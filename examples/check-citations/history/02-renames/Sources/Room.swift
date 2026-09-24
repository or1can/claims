struct Room {
    // Replaces `loadWidget`, which read the whole file into memory.
    func loadGadget() -> Gadget {
        Gadget(streaming: path)
    }
}
