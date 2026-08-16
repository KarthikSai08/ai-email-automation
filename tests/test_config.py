from gmail_access import config


def test_project_root_resolves_to_repo_root():
    assert config.PROJECT_ROOT.name == "Email_Automation"


def test_config_and_data_dirs_exist():
    assert config.CONFIG_DIR.is_dir()
    assert config.DATA_DIR.is_dir()
    assert config.CREDENTIALS_FILE.is_file()
    assert config.TOKEN_FILE.is_file()


def test_runtime_state_files_exist():
    assert config.HISTORY_FILE.is_file()
    assert config.PROCESSED_FILE.is_file()
