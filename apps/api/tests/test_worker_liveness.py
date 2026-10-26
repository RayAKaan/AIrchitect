import pytest

from app.domains.lifecycle.worker_liveness import WorkerLiveness


def test_worker_liveness_normalizes_identity():
    signal = WorkerLiveness.for_worker(" worker-1 ")
    assert signal.worker_id == "worker-1"


def test_worker_liveness_rejects_blank_identity():
    with pytest.raises(ValueError):
        WorkerLiveness.for_worker("   ")
