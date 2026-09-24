struct Room {
    /// Whether `canRestoreInPlace` is allowed: false while a plugin holds
    /// a veto over the restore.
    /// The plugin that vetoed the last restore, if any.
    var restoreBlocker: Plugin?

    func canRestoreInPlace() -> Bool {
        restoreBlocker == nil
    }
}
