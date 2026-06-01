# NSLS-II Facility API

This is the repository for the NSLS-II Facility API codebase.

## Current Status

[![Integration Tests for Deployed API](https://github.com/NSLS2/nsls2api/actions/workflows/test-production-deployment.yml/badge.svg)](https://github.com/NSLS2/nsls2api/actions/workflows/test-production-deployment.yml)

[![Integration Tests for DEV API](https://github.com/NSLS2/nsls2api/actions/workflows/test-dev-deployment.yml/badge.svg)](https://github.com/NSLS2/nsls2api/actions/workflows/test-dev-deployment.yml)

[![Data Consistency Checks between DEV and PROD APIs](https://github.com/NSLS2/nsls2api/actions/workflows/data-consistency-workflow.yml/badge.svg)](https://github.com/NSLS2/nsls2api/actions/workflows/data-consistency-workflow.yml)


## Developer Notes

In order to develop locally you will need to have a local MongoDB running.  
This can be installed using your preferred method, a native install
or [running a container](https://hub.docker.com/_/mongo) work perfectly fine.

Once you have MongoDB up and running you then need to 'seed' the facility and beamline information that
does not get pulled from any other source.

The files for the collections can be found within the `/nsls2/software/dssi/nsls2core/nsls2core-development.tgz`

1. Copy and unpack the archive into a directory (e.g. `nsls2core-development`) to your development machine

2. Import facility information into the local mongodb```
   ```bash
   mongorestore --uri="mongodb://localhost:27017" --nsFrom=nsls2core-development.facilities --nsTo=nsls2core-development.facilities ./nsls2core-development/facilities.bson
   ```
3. Import beamline information into the local mongodb
   ```bash
   mongorestore --uri="mongodb://localhost:27017" --nsFrom=nsls2core-development.beamlines --nsTo=nsls2core-development.beamlines ./nsls2core-development/beamlines.bson
   ```

You will then need to create a `.env` file that contains the configuration (an example can also be found in the same
directory as the json files).

1. Copy `/nsls2/software/dssi/nsls2core/.env.development` to your local machine
2. Rename to `.env` and place in the `src/nsls2api` directory in your cloned repo (in the same folder as `main.py`)
3. Ensure that you have the `bnlroot.crt` file (which is deployed to all BNL managed machines) in the location specified
   within the `.env` file.

### Code Style

This project uses `ruff` to format the code - in order to run the formatter simply type:
```bash
   uvx ruff format
```
### Code Linting

This project uses `ruff` to check the code - in order to run the linter simply type:
```bash
   uvx ruff check
```


### Updating Dependencies

The project uses `uv pip compile` to manage the `requirements.txt` and `requirements-dev.txt` files.

In order to upgrade the packages versions you will need to simply run

```
uv pip compile requirements-dev.in --upgrade -o requirements-dev.txt --exclude-newer "1 week"
uv pip compile requirements.in --upgrade -o requirements.txt --exclude-newer "1 week"
```

Then in order to actually upgrade the packages 
```
uv pip install -r requirements-dev.txt
uv pip install -r requirements.txt
```
Of course, you can drop the `uv` from these last commands if you want to wait longer. 
