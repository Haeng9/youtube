from app.jobs.queue import create_job, get_job, update_job, JobStatus


def test_create_and_get_job():
    job = create_job("test.mp3", "jazz")
    assert job.job_id is not None
    fetched = get_job(job.job_id)
    assert fetched.status == "pending"
    assert fetched.filename == "test.mp3"


def test_update_job():
    job = create_job("test2.mp3", "pop")
    update_job(job.job_id, JobStatus.PROCESSING, "진행중...")
    fetched = get_job(job.job_id)
    assert fetched.status == "processing"
    assert fetched.message == "진행중..."
