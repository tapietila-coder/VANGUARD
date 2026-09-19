"""Job Queue: a real local, in-process job system backed by a small
ThreadPoolExecutor (see queue.py) executing real registered job types
(see job_types.py) against real VANGUARD state. Not a distributed queue —
same single-node reference posture as the rest of this project."""
