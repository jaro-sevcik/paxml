# coding=utf-8
# Copyright 2022 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for metric_utils."""
from typing import Any, Dict, List, Tuple, Union

import os
from absl.testing import absltest

import clu.metrics as clu_metrics
import clu.values as clu_values
import flax
import numpy as np
from paxml import metric_utils
from paxml import summary_utils


@flax.struct.dataclass
class MockMetric(clu_metrics.Metric):
  """A mock metric where all the data is empty."""

  @classmethod
  def from_model_output(cls) -> clu_metrics.Metric:
    return MockMetric()

  def merge(self, other: clu_metrics.Metric) -> clu_metrics.Metric:
    return MockMetric()

  def compute(self) -> None:
    return None

  def compute_value(self) -> clu_values.Value:
    raise NotImplementedError('Other mock metrics should define this.')


def _mock_image(batch_size=None) -> clu_values.Image:
  base_shape = [12, 12, 3]
  if batch_size:
    base_shape = [batch_size] + base_shape
  return clu_values.Image(np.ones(base_shape))


class MetricUtilsTest(absltest.TestCase):

  def _test_dir(self):
    return os.path.join(absltest.get_default_test_tmpdir(), 'summary')

  def test_scalar_compute_metric_values(self):
    class ScalarMetric(MockMetric):

      def compute_value(self) -> clu_values.Scalar:
        return clu_values.Scalar(5)

    metrics = {'test': ScalarMetric()}
    test_dir = self._test_dir()

    metric_values = metric_utils.compute_metric_values(metrics)
    self.assertIn('test', metric_values)
    self.assertEqual(metric_values['test'].value, 5)

    with summary_utils.get_summary_writer(test_dir):
      metric_utils.write_clu_metric_summaries(metric_values, step_i=0)

  def test_list_compute_metric_values(self):
    class ScalarListMetric(MockMetric):

      def compute_value(self) -> List[Any]:
        return [
            clu_values.Scalar(5),
            clu_values.Text('hi'),
            _mock_image(batch_size=None),
            _mock_image(batch_size=2)
        ]
    metrics = {'test': ScalarListMetric()}

    metric_values = metric_utils.compute_metric_values(metrics)
    self.assertEqual(metric_values['test/test_0'].value, 5)
    self.assertEqual(metric_values['test/test_1'].value, 'hi')
    self.assertEqual(metric_values['test/test_2'].value.shape, (12, 12, 3))
    self.assertEqual(metric_values['test/test_3'].value.shape, (2, 12, 12, 3))

  def test_tuple_compute_metric_values(self):
    class ScalarTupleMetric(MockMetric):

      def compute_value(self) -> Tuple[Any]:
        return (clu_values.Scalar(5), clu_values.Text('hi'))
    metrics = {'test': ScalarTupleMetric()}

    metric_values = metric_utils.compute_metric_values(metrics)
    self.assertEqual(metric_values['test/test_0'].value, 5)
    self.assertEqual(metric_values['test/test_1'].value, 'hi')

  def test_scalar_dict_comptue_metric_values(self):
    class ScalarDictMetric(MockMetric):

      def compute_value(self) -> Dict[str, Any]:
        return {
            'scalar_0': clu_values.Scalar(1),
            'scalar_1': clu_values.Scalar(2),
            'text_0': clu_values.Text('test3'),
            'image_0': _mock_image(None),
            'image_1': _mock_image(5)
        }

    metrics = {'test': ScalarDictMetric()}

    metric_values = metric_utils.compute_metric_values(metrics)
    self.assertEqual(metric_values['test/scalar_0'].value, 1)
    self.assertEqual(metric_values['test/scalar_1'].value, 2)
    self.assertEqual(metric_values['test/text_0'].value, 'test3')
    self.assertEqual(metric_values['test/image_0'].value.shape, (12, 12, 3))
    self.assertEqual(metric_values['test/image_1'].value.shape, (5, 12, 12, 3))

  def test_mixed_dict_compute_metric_values(self):
    class MixedDictMetric(MockMetric):

      def compute_value(self) -> Dict[str, Any]:
        return {
            'scalar_0': clu_values.Scalar(1),
            'list_0': [clu_values.Scalar(1), clu_values.Scalar(2)],
            'list_1': [clu_values.Scalar(1), clu_values.Text('test')],
            'tuple_0': (_mock_image(None), _mock_image(5)),
            'image_0': _mock_image(5),
        }

    metrics = {'test': MixedDictMetric()}
    metric_values = metric_utils.compute_metric_values(metrics)
    self.assertEqual(metric_values['test/scalar_0'].value, 1)
    # First list is two scalars.
    self.assertEqual(metric_values['test/list_0_0'].value, 1)
    self.assertEqual(metric_values['test/list_0_1'].value, 2)
    # Secont list is a scalar and text.
    self.assertEqual(metric_values['test/list_1_0'].value, 1)
    self.assertEqual(metric_values['test/list_1_1'].value, 'test')
    # Third list is two images, one unbatched, and one batched.
    self.assertEqual(metric_values['test/tuple_0_0'].value.shape, (12, 12, 3))
    self.assertEqual(
        metric_values['test/tuple_0_1'].value.shape, (5, 12, 12, 3))
    # Finally we just have an image.
    self.assertEqual(metric_values['test/image_0'].value.shape, (5, 12, 12, 3))

  def test_write_clu_metric_summaries(self):
    class MixedDictMetric(MockMetric):

      def compute_value(self) -> Dict[str, Any]:
        return {
            'scalar_0': clu_values.Scalar(1),
            'list_0': [clu_values.Scalar(1), clu_values.Scalar(2)],
            'list_1': [clu_values.Scalar(1), clu_values.Text('test')],
            'tuple_0': (_mock_image(None), _mock_image(5)),
            'image_0': _mock_image(5),
        }

    metrics = {'test': MixedDictMetric()}
    metric_values = metric_utils.compute_metric_values(metrics)
    test_dir = self._test_dir()
    with summary_utils.get_summary_writer(test_dir):
      metric_utils.write_clu_metric_summaries(metric_values, step_i=0)


if __name__ == '__main__':
  absltest.main()
