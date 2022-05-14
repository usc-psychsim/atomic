class TimePeriod:

    def __init__(self, start, end):
        if start is None:
            start = 0
        if start < 0:
            raise Exception(f"Start time must not be negative (negative means unknown). {start}")
        if 0 <= end < start:
            raise Exception(f"End time must not be earlier than start time for a time period. {end}")
        self.__start = start
        self.__end = end

    @property
    def start(self):
        return self.__start

    @property
    def end(self):
        return self.__end

    @end.setter
    def end(self, end_time):
        self.__end = end_time

    @property
    def duration(self):
        if self.end < 0:
            return None
        return self.end - self.start

    @property
    def has_ended(self):
        return self.__end is not None and self.__end >= 0.0

    @property
    def ongoing(self):
        return self.__end is None or self.__end < 0.0

    def to_string(self):
        if self.has_ended:
            return "from " + str(self.start) + " to " + str(self.end)
        else:
            return "from " + str(self.start) + " ongoing"

    def __repr__(self):
        return self.to_string()

    def __eq__(self, other):
        return self.start == other.start and self.end == other.end


def does_overlap(time_period_1, time_period_2):
    if time_period_1.start <= time_period_2.start <= time_period_1.end:
        return True
    if time_period_1.start <= time_period_2.end <= time_period_1.end:
        return True
    if time_period_2.start <= time_period_1.start <= time_period_2.end:
        return True
    if time_period_2.start <= time_period_1.end <= time_period_2.end:
        return True
    if time_period_1.start == time_period_2.start and time_period_1.end == time_period_2.end:
        return True
    if time_period_1.start > time_period_2.end or time_period_1.end < time_period_2.start:
        return False

    print("WARNING: time period did not match overlap options: " + time_period_1.to_string() + " and " + time_period_2.to_string())
    return False


def get_overlap_union(time_period_1, time_period_2):
    start = min(time_period_1.start, time_period_2.start)
    end = max(time_period_1.end, time_period_2.end)
    return TimePeriod(start, end)


def get_non_overlap_union(time_period_1, time_period_2):
    if does_overlap(time_period_1, time_period_2):
        current_set = [time_period_1, time_period_2]
        current_set.sort(reverse=True, key=lambda x: (x.start, x.end))
        final_set = []
        while len(current_set) > 0:
            if len(final_set) == 0:
                time_period = current_set.pop()
                final_set.append(time_period)
            else:
                time_period = current_set.pop()
                previous_time_period = final_set.pop()
                if does_overlap(time_period, previous_time_period):
                    new_1 = TimePeriod(previous_time_period.start, time_period.start)
                    if previous_time_period.end <= time_period.end:
                        new_2 = TimePeriod(previous_time_period.end, time_period.end)
                    else:
                        new_2 = TimePeriod(time_period.end, previous_time_period.end)
                    final_set.append(new_1)
                    final_set.append(new_2)
                else:
                    final_set.append(previous_time_period)
                    final_set.append(time_period)
        return final_set
    else:
        return [time_period_1, time_period_2]


def contains_overlapping_set(time_periods):
    time_periods_copy = time_periods.copy()
    time_periods_copy.sort(reverse=True, key=lambda x: (x.start, x.end))
    while len(time_periods_copy) > 1:
        time_period = time_periods_copy.pop()
        for remaining_time_period in time_periods_copy:
            if does_overlap(time_period, remaining_time_period):
                return True
    return False


# This one includes periods of overlapping activity
# This is used to calculate the full activity duration, regardless is there is overlapping effort
def get_non_overlapping_set(time_period_set):
    if contains_overlapping_set(time_period_set):
        non_overlapping_set = []
        time_periods_copy = time_period_set.copy()
        time_periods_copy.sort(reverse=True, key=lambda x: (x.start, x.end))
        while len(time_periods_copy) > 0:
            time_period = time_periods_copy.pop()
            if len(non_overlapping_set) == 0:
                non_overlapping_set.append(time_period)
            else:
                last_non_overlapping_time_period = non_overlapping_set.pop()
                if does_overlap(time_period, last_non_overlapping_time_period):
                    merged_time_period = get_overlap_union(time_period, last_non_overlapping_time_period)
                    non_overlapping_set.append(merged_time_period)
                else:
                    non_overlapping_set.append(last_non_overlapping_time_period)
                    non_overlapping_set.append(time_period)
        return non_overlapping_set

    return time_period_set


# This one does not include periods of overlapping activity
# This is used to calculate man-hour efficiency ratio
def get_uniquely_non_overlapping_set(time_period_set):
    if contains_overlapping_set(time_period_set):
        non_overlapping_set = []
        time_periods_copy = time_period_set.copy()
        time_periods_copy.sort(reverse=True, key=lambda x: (x.start, x.end))
        while len(time_periods_copy) > 0:
            time_period = time_periods_copy.pop()
            if len(non_overlapping_set) == 0:
                non_overlapping_set.append(time_period)
            else:
                last_non_overlapping_time_period = non_overlapping_set.pop()
                if does_overlap(time_period, last_non_overlapping_time_period):
                    non_overlap_set = get_non_overlap_union(time_period, last_non_overlapping_time_period)
                    non_overlapping_set += non_overlap_set
                else:
                    non_overlapping_set.append(last_non_overlapping_time_period)
                    non_overlapping_set.append(time_period)
        return non_overlapping_set

    return time_period_set


def get_sum_of_durations(time_period_set):
    duration = 0
    for time_period in time_period_set:
        duration += time_period.duration
    return duration

