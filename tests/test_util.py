from pathlib import Path

import pytest

from mammos_parser import util


def test_collected():
    # empty is allowed
    root = Path("/my/dataset/root")

    c1 = util.Collected(root, True, {"file-1"}, {"subdir-1", "subdir-2"})
    c2 = util.Collected(root, True, {"subdir-1/file-1"}, set())
    c3 = util.Collected(
        root,
        False,
        {"subdir-2/file-1", "subdir-2/file2"},
        {"subdir-2/subdir-3"},
    )

    assert c1
    assert c2
    assert not c3

    c12 = c1 + c2
    assert c12
    assert c12.collected_files == {"file-1", "subdir-1/file-1"}
    assert c12.collected_dirs == {"subdir-1", "subdir-2"}

    c13 = c1 + c3
    assert not c13
    assert c13.collected_files == {
        "file-1",
        "subdir-2/file-1",
        "subdir-2/file2",
    }
    assert c13.collected_dirs == {
        "subdir-1",
        "subdir-2",
        "subdir-2/subdir-3",
    }

    c123 = c1 + c2 + c3
    assert not c123
    assert c123.collected_files == {
        "file-1",
        "subdir-1/file-1",
        "subdir-2/file-1",
        "subdir-2/file2",
    }
    assert c123.collected_dirs == {
        "subdir-1",
        "subdir-2",
        "subdir-2/subdir-3",
    }

    assert c13.collected_dirs == {
        "subdir-1",
        "subdir-2",
        "subdir-2/subdir-3",
    }
    with pytest.raises(ValueError):
        c1 + util.Collected("/abc", True, set(), set())


def test_check_directory_empty(tmp_path: Path):
    c = util.check_directory(tmp_path, ".")
    assert c
    assert c.collected_files == set()
    assert c.collected_dirs == set()


def test_check_directory_exceptions():
    with pytest.raises(ValueError):
        util.check_directory(Path("my/dataset/root"), ".")


def test_check_directory_required_files_only_one_file(tmp_path: Path):
    (tmp_path / "file-1").touch()
    c = util.check_directory(tmp_path, ".", required_files={"file-1"})
    assert c
    assert c.collected_files == {"file-1"}
    assert c.collected_dirs == set()

    c = util.check_directory(tmp_path, ".", required_files={"file-2"})
    assert not c
    assert c.collected_files == set()
    assert c.collected_dirs == set()


def test_check_directory_required_files_only_multiple_files(tmp_path: Path):
    (tmp_path / "file-1").touch()
    (tmp_path / "file-2").touch()
    c = util.check_directory(tmp_path, ".", required_files={"file-1"})
    assert not c
    assert c.collected_files == {"file-1"}
    assert c.collected_dirs == set()

    c = util.check_directory(tmp_path, ".", required_files={"file-1", "file-2"})
    assert c
    assert c.collected_files == {"file-1", "file-2"}
    assert c.collected_dirs == set()

    c = util.check_directory(
        tmp_path, ".", required_files={"file-1", "file-2", "file-3"}
    )
    assert not c
    assert c.collected_files == {"file-1", "file-2"}
    assert c.collected_dirs == set()

    c = util.check_directory(tmp_path, ".", required_files={"file-1", "file-3"})
    assert not c
    assert c.collected_files == {"file-1"}
    assert c.collected_dirs == set()


def test_check_directory_optional_files_only(tmp_path: Path):
    c = util.check_directory(tmp_path, ".", optional_files={"file-1"})
    assert c
    assert c.collected_files == set()
    assert c.collected_dirs == set()

    (tmp_path / "file-1").touch()
    c = util.check_directory(tmp_path, ".", optional_files={"file-1"})
    assert c
    assert c.collected_files == {"file-1"}
    assert c.collected_dirs == set()

    (tmp_path / "file-1").touch()
    (tmp_path / "file-2").touch()

    c = util.check_directory(tmp_path, ".", optional_files={"file-1", "file-2"})
    assert c
    assert c.collected_files == {"file-1", "file-2"}
    assert c.collected_dirs == set()

    c = util.check_directory(
        tmp_path, ".", optional_files={"file-1", "file-2", "file-3"}
    )
    assert c
    assert c.collected_files == {"file-1", "file-2"}
    assert c.collected_dirs == set()

    c = util.check_directory(tmp_path, ".", optional_files={"file-1", "file-3"})
    assert not c
    assert c.collected_files == {"file-1"}
    assert c.collected_dirs == set()


def test_check_directory_file_choices_only(tmp_path: Path):
    c = util.check_directory(
        tmp_path, ".", required_files_from_choices=[{"file-1", "file-2"}]
    )
    assert not c
    assert c.collected_files == set()
    assert c.collected_dirs == set()

    (tmp_path / "file-1").touch()

    c = util.check_directory(
        tmp_path, ".", required_files_from_choices=[{"file-1", "file-2"}]
    )
    assert c
    assert c.collected_files == {"file-1"}
    assert c.collected_dirs == set()

    (tmp_path / "file-2").touch()

    c = util.check_directory(
        tmp_path, ".", required_files_from_choices=[{"file-1", "file-2"}]
    )
    assert not c
    assert c.collected_files == set()
    assert c.collected_dirs == set()

    c = util.check_directory(
        tmp_path, ".", required_files_from_choices=[{"file-1", "file-3"}]
    )
    assert not c
    assert c.collected_files == {"file-1"}
    assert c.collected_dirs == set()

    c = util.check_directory(
        tmp_path, ".", required_files_from_choices=[{"file-1"}, {"file-2"}]
    )
    assert c
    assert c.collected_files == {"file-1", "file-2"}
    assert c.collected_dirs == set()


def test_check_directory_file_pairs_only(tmp_path: Path):
    c = util.check_directory(tmp_path, ".", required_file_pairs=[("in-", "out-")])
    assert not c
    assert c.collected_files == set()
    assert c.collected_dirs == set()

    (tmp_path / "in-1").touch()
    (tmp_path / "out-1").touch()

    c = util.check_directory(tmp_path, ".", required_file_pairs=[("in-", "out-")])
    assert c
    assert c.collected_files == {"in-1", "out-1"}
    assert c.collected_dirs == set()

    (tmp_path / "in-2").touch()

    c = util.check_directory(tmp_path, ".", required_file_pairs=[("in-", "out-")])
    assert not c
    assert c.collected_files == {"in-1", "out-1"}
    assert c.collected_dirs == set()

    (tmp_path / "out-2").touch()

    c = util.check_directory(tmp_path, ".", required_file_pairs=[("in-", "out-")])
    assert c
    assert c.collected_files == {
        "in-1",
        "out-1",
        "in-2",
        "out-2",
    }
    assert c.collected_dirs == set()

    (tmp_path / "b.txt").touch()

    c = util.check_directory(
        tmp_path, ".", required_file_pairs=[("in-", "out-"), ("a", "b")]
    )
    assert not c
    assert c.collected_files == {
        "in-1",
        "out-1",
        "in-2",
        "out-2",
    }
    assert c.collected_dirs == set()

    (tmp_path / "a.txt").touch()

    c = util.check_directory(
        tmp_path, ".", required_file_pairs=[("in-", "out-"), ("a", "b")]
    )
    assert c
    assert c.collected_files == {
        "in-1",
        "out-1",
        "in-2",
        "out-2",
        "a.txt",
        "b.txt",
    }
    assert c.collected_dirs == set()


def test_check_directory_required_dirs_only(tmp_path: Path):
    c = util.check_directory(tmp_path, ".", required_subdirs={"dir-1"})
    assert not c
    assert c.collected_files == set()
    assert c.collected_dirs == set()

    (tmp_path / "dir-1").mkdir()
    c = util.check_directory(tmp_path, ".", required_subdirs={"dir-1"})
    assert c
    assert c.collected_files == set()
    assert c.collected_dirs == {"dir-1"}

    (tmp_path / "dir-2").mkdir()
    c = util.check_directory(tmp_path, ".", required_subdirs={"dir-1"})
    assert not c
    assert c.collected_files == set()
    assert c.collected_dirs == {"dir-1"}

    c = util.check_directory(tmp_path, ".", required_subdirs={"dir-1", "dir-2"})
    assert c
    assert c.collected_files == set()
    assert c.collected_dirs == {"dir-1", "dir-2"}


def test_check_directory_optional_dirs_only(tmp_path: Path):
    c = util.check_directory(tmp_path, ".", optional_subdirs={"dir-1"})
    assert c
    assert c.collected_files == set()
    assert c.collected_dirs == set()

    (tmp_path / "dir-1").mkdir()
    c = util.check_directory(tmp_path, ".", optional_subdirs={"dir-1"})
    assert c
    assert c.collected_files == set()
    assert c.collected_dirs == {"dir-1"}

    c = util.check_directory(tmp_path, ".", optional_subdirs={"dir-1", "dir-2"})
    assert c
    assert c.collected_files == set()
    assert c.collected_dirs == {"dir-1"}

    (tmp_path / "dir-2").mkdir()
    c = util.check_directory(tmp_path, ".", optional_subdirs={"dir-1", "dir-2"})
    assert c
    assert c.collected_files == set()
    assert c.collected_dirs == {"dir-1", "dir-2"}

    c = util.check_directory(tmp_path, ".", optional_subdirs={"dir-1"})
    assert not c
    assert c.collected_files == set()
    assert c.collected_dirs == {"dir-1"}


def test_check_directory_full(tmp_path: Path):
    # TODO capture and check logging
    c = util.check_directory(
        tmp_path,
        ".",
        required_files={"file-req"},
        optional_files={"file-opt"},
        required_files_from_choices=[{"choice-1", "choice-2"}],
        required_file_pairs=[("a-", "b-")],
        required_subdirs={"req-dir"},
        optional_subdirs={"opt-dir"},
    )
    assert not c
    assert c.collected_files == set()
    assert c.collected_dirs == set()

    (tmp_path / "file-req").touch()
    (tmp_path / "choice-1").touch()
    (tmp_path / "a-file").touch()
    (tmp_path / "b-file").touch()
    (tmp_path / "dir-req").mkdir()

    c = util.check_directory(
        tmp_path,
        ".",
        required_files={"file-req"},
        optional_files={"file-opt"},
        required_files_from_choices=[{"choice-1", "choice-2"}],
        required_file_pairs=[("a-", "b-")],
        required_subdirs={"dir-req"},
        optional_subdirs={"dir-opt"},
    )
    assert c
    assert c.collected_files == {
        "file-req",
        "choice-1",
        "a-file",
        "b-file",
    }
    assert c.collected_dirs == {"dir-req"}

    (tmp_path / "file-opt").touch()
    (tmp_path / "dir-opt").mkdir()

    c = util.check_directory(
        tmp_path,
        ".",
        required_files={"file-req"},
        optional_files={"file-opt"},
        required_files_from_choices=[{"choice-1", "choice-2"}],
        required_file_pairs=[("a-", "b-")],
        required_subdirs={"dir-req"},
        optional_subdirs={"dir-opt"},
    )
    assert c
    assert c.collected_files == {
        "file-req",
        "choice-1",
        "a-file",
        "b-file",
        "file-opt",
    }
    assert c.collected_dirs == {"dir-req", "dir-opt"}

    (tmp_path / "file-not-wanted").touch()
    c = util.check_directory(
        tmp_path,
        ".",
        required_files={"file-req"},
        optional_files={"file-opt"},
        required_files_from_choices=[{"choice-1", "choice-2"}],
        required_file_pairs=[("a-", "b-")],
        required_subdirs={"dir-req"},
        optional_subdirs={"dir-opt"},
    )
    assert not c
    assert c.collected_files == {
        "file-req",
        "choice-1",
        "a-file",
        "b-file",
        "file-opt",
    }
    assert c.collected_dirs == {"dir-req", "dir-opt"}


def test_check_directory_full_relative(tmp_path: Path):
    (tmp_path / "my_base/mysub").mkdir(parents=True)
    (tmp_path / "my_base/mysub" / "file-req").touch()
    (tmp_path / "my_base/mysub" / "choice-1").touch()
    (tmp_path / "my_base/mysub" / "a-file").touch()
    (tmp_path / "my_base/mysub" / "b-file").touch()
    (tmp_path / "my_base/mysub" / "dir-req").mkdir()
    (tmp_path / "my_base/mysub" / "file-opt").touch()
    (tmp_path / "my_base/mysub" / "dir-opt").mkdir()

    c = util.check_directory(
        tmp_path,
        "my_base/mysub",
        required_files={"file-req"},
        optional_files={"file-opt"},
        required_files_from_choices=[{"choice-1", "choice-2"}],
        required_file_pairs=[("a-", "b-")],
        required_subdirs={"dir-req"},
        optional_subdirs={"dir-opt"},
    )
    assert c
    assert c.root_dir == tmp_path
    assert c.collected_files == {
        "my_base/mysub/file-req",
        "my_base/mysub/choice-1",
        "my_base/mysub/a-file",
        "my_base/mysub/b-file",
        "my_base/mysub/file-opt",
    }
    assert c.collected_dirs == {
        "my_base/mysub/dir-req",
        "my_base/mysub/dir-opt",
    }
