# lovdata-loader

Download and parse Lovdata's public-data archives into the snapshot
directory this repo's publishing pipeline consumes: one JSON per law or
forskrift under `snapshot/laws/`, plus `snapshot/amendments.db` built
from Norsk Lovtidend avd. 1.

```bash
pip install -e "lovdata-loader/[test]"
lovdata-load --download --output snapshot
python -m pytest lovdata-loader/tests/
```

Part of [norwegian-laws](https://github.com/sondreskarsten/norwegian-laws).
MIT licensed; the parsed data itself is NLOD 2.0 (Lovdata).
