# Dash Emulator Universal

This version of the DASH Headless Player can play dash videos over several different configurations.

## Supported Features

- 360 degree videos
- Live Streaming
- QUIC and TCP supported
- Streaming from local file system
- Bandwidth throttled streaming
- 3 different ABR algorithms - Bandwidth-based, Buffer-based and Hybrid
- Downloaded file saver
- Statistics Collector
- 2 different BW Estimation methods - Segment-based and instantaneous


## How to build

```bash
# Install package
pip install .
```

## How to Run 

### Basic with default modules
```bash
iplay -i <MPD_FILE_PATH>
```