import logging

from sklearn.linear_model import LinearRegression

from atomic.analytic import AnalyticComponent

class TeamScorePredictor(AnalyticComponent):
    TRAIN_TIMES = [4, 9, 14]
    TEST_TIMES = [4, 9, 14]

    def __init__(self, ignore=[], logger=logging):
        super().__init__(name='team_performance', y_fields=['Team Score'], team=True, ignore=ignore, 
            y_type='State', logger=logging)


    def build_model(self, X, y):
        return LinearRegression().fit(X, y)

    def output(self, model, X, participants):
        return {participants.iloc[row]: value for row, value in enumerate(model.predict(X))}
        
class MapInference(AnalyticComponent):
    TRAIN_TIMES = [2, 7, 12]
    TEST_TIMES = [2, 7, 12]

    def __init__(self, ignore=[], logger=logging):
        super().__init__(name='participant_map', y_fields=['Map'], team=False, ignore=ignore, 
            y_type='State', logger=logging)

class MarkerInference(AnalyticComponent):
    TRAIN_TIMES = [15]
    TEST_TIMES = [3, 8, 13]

    def __init__(self, ignore=[], logger=logging):
        super().__init__(name='participant_block_legend', y_fields=['Marker Legend'], team=False, ignore=ignore, 
            y_type='State', logger=logging)


STUDY2_METRICS = {'M1': TeamScorePredictor, 'M3': MapInference, 'M6': MarkerInference}
