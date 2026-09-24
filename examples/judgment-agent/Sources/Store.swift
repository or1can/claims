struct Store {
    func readRecord(key: String) -> Record? {
        cache[key]
    }
}
