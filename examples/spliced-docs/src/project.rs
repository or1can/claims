/// Loads the project at `path`, which is what `load_project` reads from
/// disk before anything else runs.
/// The manifest a project is read from.
pub struct Manifest {
    path: PathBuf,
}

pub fn load_project(path: &Path) -> Project {
    Project::from(Manifest { path: path.to_owned() })
}
