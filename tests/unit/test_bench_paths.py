from benchmarks.bench_paths import display_target


def test_display_target_excludes_user_info_and_preserves_host_port():
    assert (
        display_target("https://portfolio-user:secret@example.test:8443/path")
        == "https://example.test:8443"
    )


def test_display_target_brackets_ipv6_host():
    assert display_target("http://user:secret@[2001:db8::1]:8080") == (
        "http://[2001:db8::1]:8080"
    )
