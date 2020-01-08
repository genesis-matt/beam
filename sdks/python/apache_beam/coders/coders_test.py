#
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# pytype: skip-file

from __future__ import absolute_import

import base64
import logging
import unittest
from builtins import object

from apache_beam.coders import proto2_coder_test_messages_pb2 as test_message
from apache_beam.coders import coders
from apache_beam.coders.avro_record import AvroRecord
from apache_beam.coders.typecoders import registry as coders_registry


class PickleCoderTest(unittest.TestCase):

  def test_basics(self):
    v = ('a' * 10, 'b' * 90)
    pickler = coders.PickleCoder()
    self.assertEqual(v, pickler.decode(pickler.encode(v)))
    pickler = coders.Base64PickleCoder()
    self.assertEqual(v, pickler.decode(pickler.encode(v)))
    self.assertEqual(
        coders.Base64PickleCoder().encode(v),
        base64.b64encode(coders.PickleCoder().encode(v)))

  def test_equality(self):
    self.assertEqual(coders.PickleCoder(), coders.PickleCoder())
    self.assertEqual(coders.Base64PickleCoder(), coders.Base64PickleCoder())
    self.assertNotEqual(coders.Base64PickleCoder(), coders.PickleCoder())
    self.assertNotEqual(coders.Base64PickleCoder(), object())


class CodersTest(unittest.TestCase):

  def test_str_utf8_coder(self):
    real_coder = coders_registry.get_coder(bytes)
    expected_coder = coders.BytesCoder()
    self.assertEqual(
        real_coder.encode(b'abc'), expected_coder.encode(b'abc'))
    self.assertEqual(b'abc', real_coder.decode(real_coder.encode(b'abc')))


# The test proto message file was generated by running the following:
#
# `cd <beam repo>`
# `cp sdks/java/core/src/proto/proto2_coder_test_message.proto
#    sdks/python/apache_beam/coders`
# `cd sdks/python`
# `protoc apache_beam/coders/proto2_coder_test_messages.proto
#    --python_out=apache_beam/coders
# `rm apache_beam/coders/proto2_coder_test_message.proto`
#
# Note: The protoc version should match the protobuf library version specified
# in setup.py.
#
# TODO(vikasrk): The proto file should be placed in a common directory
# that can be shared between java and python.
class ProtoCoderTest(unittest.TestCase):

  def test_proto_coder(self):
    ma = test_message.MessageA()
    mb = ma.field2.add()
    mb.field1 = True
    ma.field1 = u'hello world'
    expected_coder = coders.ProtoCoder(ma.__class__)
    real_coder = coders_registry.get_coder(ma.__class__)
    self.assertEqual(expected_coder, real_coder)
    self.assertEqual(real_coder.encode(ma), expected_coder.encode(ma))
    self.assertEqual(ma, real_coder.decode(real_coder.encode(ma)))


class DeterministicProtoCoderTest(unittest.TestCase):

  def test_deterministic_proto_coder(self):
    ma = test_message.MessageA()
    mb = ma.field2.add()
    mb.field1 = True
    ma.field1 = u'hello world'
    expected_coder = coders.DeterministicProtoCoder(ma.__class__)
    real_coder = (coders_registry.get_coder(ma.__class__)
                  .as_deterministic_coder(step_label='unused'))
    self.assertTrue(real_coder.is_deterministic())
    self.assertEqual(expected_coder, real_coder)
    self.assertEqual(real_coder.encode(ma), expected_coder.encode(ma))
    self.assertEqual(ma, real_coder.decode(real_coder.encode(ma)))

  def test_deterministic_proto_coder_determinism(self):
    for _ in range(10):
      keys = list(range(20))
      mm_forward = test_message.MessageWithMap()
      for key in keys:
        mm_forward.field1[str(key)].field1 = str(key)
      mm_reverse = test_message.MessageWithMap()
      for key in reversed(keys):
        mm_reverse.field1[str(key)].field1 = str(key)
      coder = coders.DeterministicProtoCoder(mm_forward.__class__)
      self.assertEqual(coder.encode(mm_forward), coder.encode(mm_reverse))


class AvroTestCoder(coders.AvroGenericCoder):
  SCHEMA = """
  {
    "type": "record", "name": "testrecord",
    "fields": [
      {"name": "name", "type": "string"},
      {"name": "age", "type": "int"}
    ]
  }
  """

  def __init__(self):
    super(AvroTestCoder, self).__init__(self.SCHEMA)


class AvroTestRecord(AvroRecord):
  pass


coders_registry.register_coder(AvroTestRecord, AvroTestCoder)


class AvroCoderTest(unittest.TestCase):

  def test_avro_record_coder(self):
    real_coder = coders_registry.get_coder(AvroTestRecord)
    expected_coder = AvroTestCoder()
    self.assertEqual(
        real_coder.encode(
            AvroTestRecord({"name": "Daenerys targaryen", "age": 23})),
        expected_coder.encode(
            AvroTestRecord({"name": "Daenerys targaryen", "age": 23}))
    )
    self.assertEqual(
        AvroTestRecord({"name": "Jon Snow", "age": 23}),
        real_coder.decode(
            real_coder.encode(
                AvroTestRecord({"name": "Jon Snow", "age": 23}))
        )
    )


class DummyClass(object):
  """A class with no registered coder."""
  def __init__(self):
    pass

  def __eq__(self, other):
    if isinstance(other, self.__class__):
      return True
    return False

  def __ne__(self, other):
    # TODO(BEAM-5949): Needed for Python 2 compatibility.
    return not self == other

  def __hash__(self):
    return hash(type(self))


class FallbackCoderTest(unittest.TestCase):

  def test_default_fallback_path(self):
    """Test fallback path picks a matching coder if no coder is registered."""

    coder = coders_registry.get_coder(DummyClass)
    # No matching coder, so picks the last fallback coder which is a
    # FastPrimitivesCoder.
    self.assertEqual(coder, coders.FastPrimitivesCoder())
    self.assertEqual(DummyClass(), coder.decode(coder.encode(DummyClass())))


if __name__ == '__main__':
  logging.getLogger().setLevel(logging.INFO)
  unittest.main()
