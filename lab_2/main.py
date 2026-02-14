from scheduler import Scheduler


if __name__ == "__main__":
    sch = Scheduler(processes_num=5, iters_num=10000)

    for _ in range(1):
        sch.test_strategies()
