# dlLogs - A Log Download Tool for Analysis and Monitoring

## Description

dlLogs is an application designed to streamline the process of downloading and analyzing combat logs from the game World of Warcraft. It downloads logs from a specific server (confidential) and allows you to quickly and efficiently convert them to JSON format.

## Prerequisites

Make sure you have Python 3.11 installed, along with the following libraries:

- `os`
- `re`
- `tqdm`
- `chardet`
- `pathlib`
- `urlparse`
- `requests`

## Configuration

Before running the script, you need to configure the following variables:

- `url_base`: Base URL of the remote server where the logs are stored. Create a file named 'url.py' in the same directory as "copy_logs.py".
- `logs_dir`: Directory where the logs will be saved. The default value is a subdirectory called "logs" in the working directory.

## Future Implementations

- [x] Completion of the download file.
- [x] Implementation of download progress bar.
- [x] Completion of the download file's docstrings.
- [x] Completion of unit tests for the download script.
- [x] Code refactoring.
- [ ] Completion of the log conversion file.
- [ ] Completion of the graphical interface.

## Usage

To run the script, simply execute the Python file `copy_logs.py`. The logs will be downloaded to the directory specified in `logs_dir`.

![](https://github.com/ValadaresX/dlLogs/blob/main/gifs/copy_logs.gif)

During execution, the script checks if all logs are present on the disk. If any logs are missing, they will be downloaded. Otherwise, a message indicating that all logs are present will be displayed.

The script also runs at regular intervals between 8 and 10 hours. During this interval, a countdown will be displayed. After the countdown ends, the script will check for and download new logs if available.

## Notes

- The script assumes that the log files are encoded in UTF-8. Otherwise, it will attempt to detect the correct encoding using the `chardet` library.
- The maximum size of each log file to be read is defined by `chunk_size`. Larger files will be read partially.
- Download progress is displayed using the `tqdm` library.
