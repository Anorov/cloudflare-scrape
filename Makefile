pep8-rules := E501,W503,W504

init:
	pip install pipenv -U
	pipenv install --dev

requirements:
	pipenv lock -r > requirements.txt
	pipenv lock --dev -r > requirements-dev.txt

test:
	# This runs all of the tests, on both Python 2 and Python 3.
	pipenv run tox --parallel auto

watch:
	# This automatically selects and re-executes only tests affected by recent changes.
	pipenv run ptw -- --testmon

retry:
	# This will retry failed tests on every file change.
	pipenv run py.test -n auto --forked --looponfail

ci:
	pipenv run py.test tests

lint:
	pipenv run flake8 --ignore $(pep8-rules) cfscrape tests setup.py

format:
	# Automatic reformatting
	pipenv run autopep8 -aaa --ignore $(pep8-rules) --in-place --recursive cfscrape tests setup.py docs

coverage:
	pipenv run py.test --cov-config .coveragerc --verbose --cov-report term --cov-report xml --cov=cfscrape tests
	pipenv run coveralls

publish:
	pip install 'twine>=1.5.0'
	python setup.py sdist bdist_wheel
	twine upload dist/*
	rm -fr build dist .egg cfscrape.egg-info
