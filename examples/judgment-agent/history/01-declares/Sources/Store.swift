struct Store {
    func fetchRecord(key: String) -> Record? {
        cache[key] ?? disk.read(key)
    }
}
