import os
import sys
import json
import logging

import pytest
from pytest import fixture

from chalice.cli import factory
from chalice.deploy.deployer import Deployer
from chalice.config import Config


@fixture
def clifactory(tmpdir):
    appdir = tmpdir.mkdir('app')
    appdir.join('app.py').write(
        '# Test app\n'
        'import chalice\n'
        'app = chalice.Chalice(app_name="test")\n'
    )
    chalice_dir = appdir.mkdir('.chalice')
    chalice_dir.join('config.json').write('{}')
    return factory.CLIFactory(str(appdir))


def assert_has_no_request_body_filter(log_name):
    log = logging.getLogger(log_name)
    assert not any(
        isinstance(f, factory.LargeRequestBodyFilter) for f in log.filters)


def assert_request_body_filter_in_log(log_name):
    log = logging.getLogger(log_name)
    assert any(
        isinstance(f, factory.LargeRequestBodyFilter) for f in log.filters)


def test_can_create_botocore_session():
    session = factory.create_botocore_session()
    assert session.user_agent().startswith('aws-chalice/')


def test_can_create_botocore_session_debug():
    log_name = 'botocore.endpoint'
    assert_has_no_request_body_filter(log_name)

    factory.create_botocore_session(debug=True)

    assert_request_body_filter_in_log(log_name)
    assert logging.getLogger('').level == logging.DEBUG


def test_can_create_botocore_session_cli_factory(clifactory):
    clifactory.profile = 'myprofile'
    session = clifactory.create_botocore_session()
    assert session.profile == 'myprofile'


def test_can_create_default_deployer(clifactory):
    session = clifactory.create_botocore_session()
    deployer = clifactory.create_default_deployer(session, None)
    assert isinstance(deployer, Deployer)


def test_can_create_config_obj(clifactory):
    obj = clifactory.create_config_obj()
    assert isinstance(obj, Config)


def test_cant_load_config_obj_with_bad_project(clifactory):
    clifactory.project_dir = 'nowhere-asdfasdfasdfas'
    with pytest.raises(RuntimeError):
        clifactory.create_config_obj()


def test_error_raised_on_unknown_config_version(clifactory):
    filename = os.path.join(
        clifactory.project_dir, '.chalice', 'config.json')
    with open(filename, 'w') as f:
        f.write(json.dumps({"version": "100.0"}))

    with pytest.raises(factory.UnknownConfigFileVersion):
        clifactory.create_config_obj()


def test_filename_and_lineno_included_in_syntax_error(clifactory):
    filename = os.path.join(clifactory.project_dir, 'app.py')
    with open(filename, 'w') as f:
        f.write("this is a syntax error\n")
    # If this app has been previously imported in another app
    # we need to remove it from the cached modules to ensure
    # we get the syntax error on import.
    sys.modules.pop('app', None)
    with pytest.raises(RuntimeError) as excinfo:
        clifactory.load_chalice_app()
    message = str(excinfo.value)
    assert 'app.py' in message
    assert 'line 1' in message
