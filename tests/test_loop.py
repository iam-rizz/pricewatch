from pricewatch.main import run_forever


def test_run_forever_jalan_berulang_dengan_interval():
    calls, sleeps = [], []
    run_forever(lambda: calls.append(1), interval_seconds=60, sleep=sleeps.append, max_runs=3)
    assert len(calls) == 3
    assert sleeps == [60, 60]


def test_run_forever_tetap_lanjut_kalau_satu_run_error():
    calls = []

    def job():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("telegram down")

    run_forever(job, interval_seconds=1, sleep=lambda _: None, max_runs=2)
    assert len(calls) == 2


def test_run_forever_log_jadwal_berikutnya(caplog):
    caplog.set_level("INFO", logger="pricewatch")
    run_forever(lambda: None, interval_seconds=600, sleep=lambda _: None, max_runs=2)
    nexts = [r.getMessage() for r in caplog.records if r.getMessage().startswith("Cek berikutnya")]
    assert len(nexts) == 1 and "UTC" in nexts[0]
