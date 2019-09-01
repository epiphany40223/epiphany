// TestDurableFiles.cpp : This file contains the 'main' function. Program execution begins and ends there.
//

#pragma warning(suppress : 4996)
#define  _CRT_OBSOLETE_NO_WARNINGS

#include <iostream>

#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <stdlib.h>

using namespace std;

const char filename1[] = "\\\\media-o3020\\pdschurch\\tempdata\\jeff-test-read.txt";
const char filename2[] = "\\\\media-o3020\\pdschurch\\tempdata\\jeff-test-write.txt";
const char filename3[] = "\\\\media-o3020\\pdschurch\\tempdata\\jeff-stop.txt";

static const char* get_timestamp(bool want_newline = false)
{
	static char ts[8192];
	const time_t now = time(NULL);
	ctime_s(ts, sizeof(ts), &now);

	// Chop off trailing newline
	if (!want_newline) {
		ts[strlen(ts) - 1] = '\0';
	}

	return ts;
}

static FILE* openit(const char* filename, const char *mode, bool errors_ok = false)
{
	FILE* fp = NULL;
	const char* ts = get_timestamp();

	fp = _fsopen(filename, mode, _SH_DENYNO);
	if (NULL == fp) {
		cerr << ts << ": Cannot open file '" << filename << endl;
		if (!errors_ok) {
			exit(1);
		}
		return NULL;
	}

	cout << ts << ": Opened file " << filename << endl;
	return fp;
}

static void read_file(FILE* fp, const char *filename)
{
	// Find the length of the file
	fseek(fp, 0, SEEK_END);
	size_t file_length = ftell(fp);

	// Go back to beginning of file
	fseek(fp, 0, SEEK_SET);

	const char* ts = get_timestamp();

	char buffer[8192];
	size_t read_so_far = 0;
	size_t ret;
	while (read_so_far <= file_length) {
		ret = fread(buffer, 1, sizeof(buffer), fp);
		if (ret < 0 || ferror(fp)) {
			cerr << ts << ": Error reading file" << endl;
			exit(1);
		}
		if (0 == ret) {
			break;
		}
		read_so_far += ret;
	}
	cout << get_timestamp() << ": Read " << read_so_far << " bytes (total length " << file_length << ") from file " << filename << endl;

	// Just for giggles, ask for a file that does not exist
	// (a la PDS behavior)
	openit(filename3, "r", true);
}

static void write_file(FILE* fp, const char *filename)
{
	const char* ts1 = get_timestamp(true);
	const char* ts2 = get_timestamp();

	int ret = fwrite(ts1, 1, strlen(ts1), fp);
	if (strlen(ts1) != ret) {
		cerr << ts2 << ": Failed to write " << strlen(ts1) << " bytes to file" << endl;
		exit(1);
	}
	if (0 != fflush(fp)) {
		cerr << ts2 << ": Failed to fflush to write file" << endl;
		exit(1);
	}

	cout << get_timestamp() << ": Wrote file " << filename << endl;
}

static void doit(void)
{
	FILE* fp1, * fp2;
	fp1 = openit(filename1, "rb");
	fp2 = openit(filename2, "w+t");

	cout << get_timestamp() << ": Opened both files" << endl;

	// Measured in seconds
	time_t now;
	time_t start = 0;
	time_t write_interval = (3600 + 300);

	// Measured in miliseconds
	unsigned long read_sleep = 10 * 1000;

	// Read frequently.
	// Write infrequently.
	while (1) {
		read_file(fp1, filename1);

		// Is it time to write the file?
		now = time(NULL);
		if (now - start >= write_interval) {
			write_file(fp2, filename2);

			// Restart the interval
			start = time(NULL);
		}

		::_sleep(read_sleep);
	}

	fclose(fp1);
	fclose(fp2);
}

int main()
{
	std::cout << "Hello World!\n";
	doit();
	return 0;
}
