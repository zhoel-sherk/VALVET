cd tests
coverage run -m pytest
coverage report --omit "test_*"
coverage html --omit "test_*"
