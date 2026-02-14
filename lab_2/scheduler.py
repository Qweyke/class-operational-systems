import numpy as np
import copy

from process_simulation import ProcessSimulation


class Scheduler:
    def __init__(
        self,
        processes_num,
        iters_num,
    ):
        self._iterations_to_run = iters_num
        self._processes_num = processes_num

        self._active_processes: list[ProcessSimulation] = []
        self._distribute_processes()

    def _distribute_processes(self):
        rng = np.random.default_rng(seed=13)
        for seed_incr in range(self._processes_num):
            roll = rng.random()
            if roll <= 0.7:  # IO-bound
                cpu_mu = rng.integers(5, 30)
                io_mu = rng.integers(50, 200)
            elif roll <= 0.95:  # CPU-bound
                cpu_mu = rng.integers(150, 500)
                io_mu = rng.integers(10, 40)
            else:  # Heavy
                cpu_mu = rng.integers(800, 1500)
                io_mu = rng.integers(5, 15)

            cpu_sigma = int(cpu_mu * rng.uniform(0.1, 0.25))
            io_sigma = int(io_mu * rng.uniform(0.1, 0.25))

            self._active_processes.append(
                ProcessSimulation(
                    generator=np.random.default_rng(seed=13 + seed_incr),
                    cpu_time_mean=cpu_mu,
                    cpu_time_sigma=cpu_sigma,
                    io_time_mean=io_mu,
                    io_time_sigma=io_sigma,
                )
            )

    def test_strategies(self):
        sjf_processes = copy.deepcopy(self._active_processes)
        print("*** SJF planning ***")
        self.do_sjf_planning(sjf_processes)

        fifo_processes = copy.deepcopy(self._active_processes)
        print("*** FIFO planning ***")
        self.do_fifo_planning(fifo_processes)

    def do_fifo_planning(self, processes: list[ProcessSimulation]):
        cpu_ready_queue = list(processes)
        io_bursting_queue: list[ProcessSimulation] = []
        current_time = 0

        def check_for_completed_io_burst():
            completed_io = [
                p for p in io_bursting_queue if p.io_completion_time <= current_time
            ]
            for completed_p in completed_io:
                io_bursting_queue.remove(completed_p)
                completed_p.set_new_cpu_burst_time(current_time)
                cpu_ready_queue.insert(0, completed_p)

        for _ in range(self._iterations_to_run):
            if len(cpu_ready_queue) == 0:
                current_time = min(p.io_completion_time for p in io_bursting_queue)
                check_for_completed_io_burst()

            first_in_p = cpu_ready_queue[-1]
            current_time += first_in_p.burst_time
            first_in_p.set_io_burst_time(current_time)

            # Rearrange queues
            cpu_ready_queue.remove(first_in_p)
            io_bursting_queue.insert(0, first_in_p)

            check_for_completed_io_burst()

        # Output
        turnaround_avg_sum = 0
        waiting_avg_sum = 0
        for p in processes:
            waiting_avg, turnaround_avg = p._get_avg_metrics()
            turnaround_avg_sum += turnaround_avg
            waiting_avg_sum += waiting_avg
            print(p.get_avg_metrics_string())
        print(
            f"FIFO-scheduler Waiting average: {waiting_avg_sum / self._processes_num}, Turnaround average: {turnaround_avg_sum / self._processes_num}"
        )

    def do_sjf_planning(self, processes: list[ProcessSimulation]):
        cpu_ready_queue = list(processes)
        io_bursting_queue: list[ProcessSimulation] = []
        current_time = 0

        def check_for_completed_io_burst():
            completed_io = [
                p for p in io_bursting_queue if p.io_completion_time <= current_time
            ]
            for completed_p in completed_io:
                io_bursting_queue.remove(completed_p)
                completed_p.set_new_cpu_burst_time(current_time)
                cpu_ready_queue.append(completed_p)

        for _ in range(self._iterations_to_run):
            if len(cpu_ready_queue) == 0:
                current_time = min(p.io_completion_time for p in io_bursting_queue)
                check_for_completed_io_burst()

            cpu_ready_queue.sort(key=lambda p: p.burst_time)

            # Burst the fastest process
            fastest_cpu_p = cpu_ready_queue[0]
            current_time += fastest_cpu_p.burst_time
            fastest_cpu_p.set_io_burst_time(current_time)

            # Rearrange queues
            cpu_ready_queue.remove(fastest_cpu_p)
            io_bursting_queue.append(fastest_cpu_p)

            check_for_completed_io_burst()

        # Output
        turnaround_avg_sum = 0
        waiting_avg_sum = 0
        for p in processes:
            waiting_avg, turnaround_avg = p._get_avg_metrics()
            turnaround_avg_sum += turnaround_avg
            waiting_avg_sum += waiting_avg
            print(p.get_avg_metrics_string())
        print(
            f"SJF-scheduler Waiting average: {waiting_avg_sum / self._processes_num}, Turnaround average: {turnaround_avg_sum / self._processes_num}"
        )
