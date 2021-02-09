import Foundation
import UIKit
import AsyncDisplayKit
import Display
import Postbox
import TelegramCore
import SyncCore
import AccountContext

public protocol SettingsController: class {
    func updateContext(context: AccountContext)
}

public func makePrivacyAndSecurityController(context: AccountContext) -> ViewController {
    return privacyAndSecurityController(context: context, focusOnItemTag: PrivacyAndSecurityEntryTag.autoArchive)
}
