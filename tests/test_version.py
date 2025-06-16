import mammos_parser


def test_version():
    """Check that __version__ exists and is a string."""
    assert isinstance(mammos_parser.__version__, str)
