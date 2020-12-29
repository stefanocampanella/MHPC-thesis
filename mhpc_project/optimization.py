import nevergrad as ng
import numpy as np
import pandas as pd
from subprocess import CalledProcessError, TimeoutExpired


class Parameters:

    def __init__(self, *paths):
        data = pd.DataFrame()
        for path in paths:
            data = data.append(pd.read_csv(path, index_col='name'))
        self.data = data

    @property
    def num_vars(self):
        return self.data.shape[0]

    @property
    def names(self):
        return list(self.data.index)

    @property
    def bounds(self):
        return list(zip(self.data['lower'], self.data['upper']))

    @property
    def types(self):
        return list(self.data['type'])


class Loss:

    def __init__(self, model, parameters, measure):

        self.model = model
        self.parameters = parameters
        self.criteria = measure

    def rescale_inputs(self, xs):
        names = self.parameters.names
        bounds = self.parameters.bounds
        types = self.parameters.types
        settings = {}
        for x, name, (a, b), t in zip(xs, names, bounds, types):
            y = a + x * (b - a)
            if t == 'log':
                y = 10 ** y
            settings[name] = y

        return settings, {}

    def __call__(self, *args, **kwargs):

        args, kwargs = self.rescale_inputs(*args, **kwargs)

        try:
            simulation = self.model(*args, **kwargs)
        except CalledProcessError:
            return np.nan
        except TimeoutExpired:
            return np.nan

        return self.criteria(simulation)


class NGO:

    def __init__(self, loss, **kwargs):
        self.loss = loss

        self._optimizer_instance = ng.optimizers.NGO(self.parametrization, **kwargs)

    @property
    def parametrization(self):
        shape = (self.loss.parameters.num_vars,)

        array = ng.p.Array(shape=shape, mutable_sigma=True)
        array.set_mutation(sigma=1 / 6)
        array.set_bounds(lower=0.0, upper=1.0)

        return array

    @property
    def optimizer(self):
        return self._optimizer_instance

    def __call__(self, *args, **kwargs):
        recommendation = self.optimizer.minimize(self.loss, *args, **kwargs)
        _, recommendation = self.loss.rescale_inputs(*recommendation.args)

        return recommendation

    def to_dataframe(self, recommendation, name='recommendation'):
        num_vars = self.loss.parameters.num_vars
        massage = self.loss.rescale_inputs
        _, lower = massage(np.zeros(num_vars))
        lower = pd.DataFrame.from_dict(lower, orient='index', columns=['lower'])
        _, upper = massage(np.ones(num_vars))
        upper = pd.DataFrame.from_dict(upper, orient='index', columns=['upper'])
        best = pd.DataFrame.from_dict(recommendation, orient='index', columns=[name])

        return pd.concat([lower, upper, best], axis=1)