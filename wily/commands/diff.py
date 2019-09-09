"""
Diff command.

Compares metrics between uncommitted files and indexed files.
"""
import os

from wily import logger
from wily.operators import (
    resolve_metric,
    resolve_operator,
    get_metric,
    OperatorLevel,
)
from wily.state import State
from collections import defaultdict


def diff(config, files, metrics, changes_only=True, detail=True):
    """
    Show the differences in metrics for each of the files.

    :param config: The wily configuration
    :type  config: :namedtuple:`wily.config.WilyConfig`

    :param files: The files to compare.
    :type  files: ``list`` of ``str``

    :param metrics: The metrics to measure.
    :type  metrics: ``list`` of ``str``

    :param changes_only: Only include changes files in output.
    :type  changes_only: ``bool``

    :param detail: Show details (function-level)
    :type  detail: ``bool``
    """
    config.targets = files
    files = list(files)
    state = State(config)
    last_revision = state.index[state.default_archiver].revisions[0]

    # Convert the list of metrics to a list of metric instances
    operators = {resolve_operator(metric.split(".")[0]) for metric in metrics}
    metrics = [(metric.split(".")[0], resolve_metric(metric)) for metric in metrics]
    data = {}

    # Build a set of operators
    _operators = [operator.cls(config) for operator in operators]

    cwd = os.getcwd()
    os.chdir(config.path)
    for operator in _operators:
        logger.debug(f"Running {operator.name} operator")
        data[operator.name] = operator.run(None, config)
    os.chdir(cwd)

    extra = set()
    for operator, metric in metrics:
        if detail and resolve_operator(operator).level == OperatorLevel.Object:
            for file in files:
                try:
                    extra.update(
                        [
                            (file, key)
                            for key, value in data[operator][file].items()
                            if key != metric.name
                            and isinstance(value, dict)
                        ]
                    )
                except KeyError:
                    logger.debug(f"File {file} not in cache")
                    logger.debug("Cache follows -- ")
                    logger.debug(data[operator])

    files = [(file, None) for file in files]
    files.extend(extra)
    logger.debug(files)

    results = defaultdict(dict)
    for filename, module in files:
        metrics_data = {}
        has_changes = False
        file = filename if module is None else f"{filename}:{module}"
        for operator, metric in metrics:
            try:
                current = last_revision.get(
                    config, state.default_archiver, operator, file, metric.name
                )
            except KeyError as e:
                current = "-"
            try:
                new = get_metric(data, operator, file, metric.name)
            except KeyError as e:
                new = "-"
            if new != current:
                has_changes = True
            metrics_data[metric] = {
                'old': current,
                'new': new,
            }
        if has_changes or not changes_only:
            results[filename][module] = metrics_data
        else:
            logger.debug(metrics_data)

    return results
