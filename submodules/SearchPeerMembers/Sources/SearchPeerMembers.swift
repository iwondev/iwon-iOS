import Foundation
import Postbox
import TelegramCore
import SyncCore
import SwiftSignalKit
import AccountContext

public enum SearchPeerMembersScope {
    case memberSuggestion
    case mention
}

public func searchPeerMembers(context: AccountContext, peerId: PeerId, chatLocation: ChatLocation, query: String, scope: SearchPeerMembersScope) -> Signal<[Peer], NoError> {
    if peerId.namespace == Namespaces.Peer.CloudChannel {
        return context.account.postbox.transaction { transaction -> CachedChannelData? in
            return transaction.getPeerCachedData(peerId: peerId) as? CachedChannelData
        }
        |> mapToSignal { cachedData -> Signal<([Peer], Bool), NoError> in
            if case .peer = chatLocation, let cachedData = cachedData, let memberCount = cachedData.participantsSummary.memberCount, memberCount <= 64 {
                return Signal { subscriber in
                    let (disposable, _) = context.peerChannelMemberCategoriesContextsManager.recent(postbox: context.account.postbox, network: context.account.network, accountPeerId: context.account.peerId, peerId: peerId, searchQuery: nil, requestUpdate: false, updated: { state in
                        if case .ready = state.loadingState {
                            let normalizedQuery = query.lowercased()
                            subscriber.putNext((state.list.compactMap { participant -> Peer? in
                                if participant.peer.isDeleted {
                                    return nil
                                }
                                if normalizedQuery.isEmpty {
                                    return participant.peer
                                }
                                if normalizedQuery.isEmpty {
                                    return participant.peer
                                } else {
                                    if participant.peer.indexName.matchesByTokens(normalizedQuery) {
                                        return participant.peer
                                    }
                                    if let addressName = participant.peer.addressName, addressName.lowercased().hasPrefix(normalizedQuery) {
                                        return participant.peer
                                    }
                                    
                                    return nil
                                }
                            }, true))
                        }
                    })
                    
                    return ActionDisposable {
                        disposable.dispose()
                    }
                }
                |> runOn(Queue.mainQueue())
            }
            
            return Signal { subscriber in
                switch chatLocation {
                case let .peer(peerId):
                    let (disposable, _) = context.peerChannelMemberCategoriesContextsManager.recent(postbox: context.account.postbox, network: context.account.network, accountPeerId: context.account.peerId, peerId: peerId, searchQuery: query.isEmpty ? nil : query, updated: { state in
                        if case .ready = state.loadingState {
                            subscriber.putNext((state.list.compactMap { participant in
                                if participant.peer.isDeleted {
                                    return nil
                                }
                                return participant.peer
                            }, true))
                        }
                    })
                    
                    return ActionDisposable {
                        disposable.dispose()
                    }
                case let .replyThread(replyThreadMessage):
                    let (disposable, _) = context.peerChannelMemberCategoriesContextsManager.mentions(postbox: context.account.postbox, network: context.account.network, accountPeerId: context.account.peerId, peerId: peerId, threadMessageId: replyThreadMessage.messageId, searchQuery: query.isEmpty ? nil : query, updated: { state in
                        if case .ready = state.loadingState {
                            subscriber.putNext((state.list.compactMap { participant in
                                if participant.peer.isDeleted {
                                    return nil
                                }
                                return participant.peer
                            }, true))
                        }
                    })
                    
                    return ActionDisposable {
                        disposable.dispose()
                    }
                }
            } |> runOn(Queue.mainQueue())
        }
        |> mapToSignal { result, isReady -> Signal<[Peer], NoError> in
            switch scope {
            case .mention:
                return .single(result)
            case .memberSuggestion:
                return context.account.postbox.transaction { transaction -> [Peer] in
                    var result = result
                    let normalizedQuery = query.lowercased()
                    if isReady {
                        if let channel = transaction.getPeer(peerId) as? TelegramChannel, case .group = channel.info {
                            var matches = false
                            if normalizedQuery.isEmpty {
                                matches = true
                            } else {
                                if channel.indexName.matchesByTokens(normalizedQuery) {
                                    matches = true
                                }
                                if let addressName = channel.addressName, addressName.lowercased().hasPrefix(normalizedQuery) {
                                    matches = true
                                }
                            }
                            if matches {
                                result.insert(channel, at: 0)
                            }
                        }
                    }
                    return result
                }
            }
        }
    } else {
        return searchGroupMembers(postbox: context.account.postbox, network: context.account.network, accountPeerId: context.account.peerId, peerId: peerId, query: query)
    }
}
