from ..utils.time_period import does_overlap, contains_overlapping_set, TimePeriod, get_non_overlap_union, \
    get_uniquely_non_overlapping_set


class ActivityTracker:

    def __init__(self, who, confidence, time_period):
        self.__who = who
        self.__confidence = confidence
        self.__time_period = time_period

    @property
    def who(self):
        return self.__who

    @property
    def confidence(self):
        return self.__confidence

    @property
    def time_period(self):
        return self.__time_period

    @property
    def has_ended(self):
        return self.time_period.has_ended

    @property
    def ongoing(self):
        return self.time_period.ongoing

    def to_string(self):
        string = str(self.confidence * 100) + "% sure " + str(self.who)
        if self.time_period is not None:
            string += " " + self.time_period.to_string()
        return string

    def __repr__(self):
        return self.to_string()


def does_match(activity_tracker_1, activity_tracker_2):
    if activity_tracker_1.who != activity_tracker_2.who:
        return False
    if activity_tracker_1.confidence != activity_tracker_2.confidence:
        return False
    return True


def does_time_period_overlap(activity_tracker_1, activity_tracker_2):
    if not does_match(activity_tracker_1, activity_tracker_2):  # make sure who and confidence match
        return False
    if activity_tracker_1.ongoing or activity_tracker_2.ongoing:
        if activity_tracker_1.ongoing and activity_tracker_2.ongoing and activity_tracker_1.time_period.start == activity_tracker_2.time_period.start:
            return True
        return False
    return does_overlap(activity_tracker_1.time_period, activity_tracker_2.time_period)


def get_activity_tracker_union(activity_tracker_1, activity_tracker_2):
    if not does_match(activity_tracker_1, activity_tracker_2):
        print("WARNING: activities do not match who or confidence and should: " + str(activity_tracker_1) + ": " + str(activity_tracker_2))
    start = min(activity_tracker_1.time_period.start, activity_tracker_2.time_period.start)
    end = max(activity_tracker_1.time_period.end, activity_tracker_2.time_period.end)
    merged_time_period = TimePeriod(start, end)
    return ActivityTracker(activity_tracker_1.who, activity_tracker_1.confidence, merged_time_period)


def get_activity_tracker_non_overlap_union(activity_tracker_1, activity_tracker_2):
    if not does_match(activity_tracker_1, activity_tracker_2):
        print("WARNING: activities do not match who or confidence and should: " + str(activity_tracker_1) + ": " + str(activity_tracker_2))

    time_period_1 = activity_tracker_1.time_period
    time_period_2 = activity_tracker_2.time_period
    non_overlapping_set = get_non_overlap_union(time_period_1, time_period_2)
    activity_set = []
    for time_period in non_overlapping_set:
        activity_set.append(ActivityTracker(activity_tracker_1.who, activity_tracker_1.confidence, time_period))
    return activity_set


def contains_overlapping_time_periods(activity_tracker_set):
    time_periods = []
    for activity_tracker in activity_tracker_set:
        time_periods.append(activity_tracker.time_period)
    return contains_overlapping_set(time_periods)


def get_non_overlapping_activity_tracker_set(activity_tracker_set):
    if contains_overlapping_time_periods(activity_tracker_set):
        non_overlapping_set = []
        activity_tracker_set_copy = activity_tracker_set.copy()
        activity_tracker_set_copy.sort(reverse=True, key=lambda x: (x.time_period.start, x.time_period.end))
        while len(activity_tracker_set_copy) > 0:
            activity_tracker = activity_tracker_set_copy.pop()
            if len(non_overlapping_set) == 0:
                non_overlapping_set.append(activity_tracker)
            else:
                last_non_overlapping_activity_tracker = non_overlapping_set.pop()
                if does_time_period_overlap(activity_tracker, last_non_overlapping_activity_tracker):
                    merged_activity_tracker = get_activity_tracker_union(activity_tracker, last_non_overlapping_activity_tracker)
                    non_overlapping_set.append(merged_activity_tracker)
                else:
                    non_overlapping_set.append(last_non_overlapping_activity_tracker)
                    non_overlapping_set.append(activity_tracker)
        return non_overlapping_set

    return activity_tracker_set


def get_uniquely_non_overlapping_activity_tracker_set(activity_tracker_set):
    if contains_overlapping_time_periods(activity_tracker_set):
        non_overlapping_set = []
        activity_tracker_set_copy = activity_tracker_set.copy()
        activity_tracker_set_copy.sort(reverse=True, key=lambda x: (x.time_period.start, x.time_period.end))
        while len(activity_tracker_set_copy) > 0:
            activity_tracker = activity_tracker_set_copy.pop()
            if len(non_overlapping_set) == 0:
                non_overlapping_set.append(activity_tracker)
            else:
                last_non_overlapping_activity_tracker = non_overlapping_set.pop()
                if does_time_period_overlap(activity_tracker, last_non_overlapping_activity_tracker):
                    non_overlap_set = get_activity_tracker_non_overlap_union(activity_tracker, last_non_overlapping_activity_tracker)
                    non_overlapping_set += non_overlap_set
                else:
                    non_overlapping_set.append(last_non_overlapping_activity_tracker)
                    non_overlapping_set.append(activity_tracker)
        return non_overlapping_set

    return activity_tracker_set


def get_sum_of_activity_durations(activity_tracker_set):
    if len(activity_tracker_set) == 0 or only_ongoing_activities(activity_tracker_set):
        return -1.0

    duration = 0.0
    for activity_tracker in activity_tracker_set:
        if activity_tracker.has_ended:
            duration += activity_tracker.time_period.duration
    return duration


def only_ongoing_activities(activity_tracker_set):
    for activity_tracker in activity_tracker_set:
        if activity_tracker.has_ended:
            return False
    return True
