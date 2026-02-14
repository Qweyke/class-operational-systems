import numpy as np


class ProcessSimulation:
    def __init__(
        self,
        generator: np.random.Generator,
        cpu_time_mean,
        cpu_time_sigma,
        io_time_mean,
        io_time_sigma,
    ):
        self._generator = generator
        self._cpu_time_mean = cpu_time_mean
        self._cpu_time_sigma = cpu_time_sigma
        self._io_time_mean = io_time_mean
        self._io_time_sigma = io_time_sigma

        # Metrics
        self.total_waiting_time = 0
        self.total_turnaround_time = 0
        self.iterations_passed = -1  # Start from -1 to avoid initial incr

        # CPU-operations time
        self.burst_time = 0
        self.arrival_time = 0

        # Set initial time as CPU-bound
        self.set_new_cpu_burst_time(current_time=0)

        # Timestamp for scheduler to check
        self.io_completion_time = 0

    def __str__(self):
        return f"Process ID: {id(self)}; CPU: mean {self._cpu_time_mean}, std {self._cpu_time_sigma}; IO: mean {self._io_time_mean}, std {self._io_time_sigma}."

    def set_new_cpu_burst_time(self, current_time):
        # Add full CPU-IO cycle time
        self.iterations_passed += 1
        self.total_turnaround_time += current_time - self.arrival_time

        # Generate new time, reset arrival mark
        self.burst_time = max(
            1.0,
            self._generator.normal(loc=self._cpu_time_mean, scale=self._cpu_time_sigma),
        )
        self.arrival_time = current_time

    def set_io_burst_time(self, current_time):
        # Add current waiting-for-CPU time
        self.total_waiting_time += current_time - self.arrival_time

        # Generate new time, reset completion time
        io_time_needed = max(
            1.0,
            self._generator.normal(loc=self._io_time_mean, scale=self._io_time_sigma),
        )

        self.io_completion_time = current_time + io_time_needed

    def _get_avg_metrics(self):
        if self.iterations_passed <= 0:
            return 0.0, 0.0

        return (
            self.total_waiting_time / self.iterations_passed,
            self.total_turnaround_time / self.iterations_passed,
        )

    def get_avg_metrics_string(self):
        waiting_avg, turnaround_avg = self._get_avg_metrics()
        return (
            str(self)
            + f" Waiting average: {waiting_avg}, Turnaround average: {turnaround_avg}"
        )
