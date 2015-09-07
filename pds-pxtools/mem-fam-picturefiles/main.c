#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include <string.h>
#include <ctype.h>
#include <sys/stat.h>

#include <paradox.h>


static void find_field(pxdoc_t *pxdoc, const char *fname,
                       pxfield_t **field, int *index, int *offset)
{
    struct px_field *f;
    int fo, fi;
    int num_fields = PX_get_num_fields(pxdoc);
    for (fo = fi = 0; fi < num_fields; ++fi) {
        f = PX_get_field(pxdoc, fi);
        if (strcasecmp(f->px_fname, fname) == 0) {
            *field = f;
            *index = fi;
            *offset = fo;
            return;
        }

        fo += f->px_flen;
    }
}


void update_db(const char *dbname)
{
    pxdoc_t *pxdoc;

    char *ptr;
    ptr = strrchr(dbname, '.');
    if (strcasecmp(ptr, ".DB") != 0) {
        fprintf(stderr, "%s is not a recognized database filename\n", dbname);
        fprintf(stderr, "Database filenames must end in \".DB\"\n");
        exit(1);
    }

    pxdoc = PX_new();
    PX_open_file(pxdoc, dbname);

    char *blobname;
    blobname = strdup(dbname);
    int len = strlen(blobname);
    blobname[len - 2] = 'M';
    struct stat s;
    if (stat(blobname, &s) == 0) {
        PX_set_blob_file(pxdoc, blobname);
    }

    fprintf(stderr, "%s dbname opened", dbname);

    // Find the Name and PictureFile field info
    pxfield_t *f_name, *f_picturefile;
    int fi_name, fi_picturefile;
    int offset_name, offset_picturefile;

    find_field(pxdoc, "name", &f_name, &fi_name, &offset_name);
    find_field(pxdoc, "picturefile", &f_picturefile, &fi_picturefile,
               &offset_picturefile);
    assert(f_name);
    assert(f_picturefile);

    // Traverse the records

    int recordsize = PX_get_recordsize(pxdoc);
    char *record = malloc(recordsize + 128);
    assert(record);

    int num_records = PX_get_num_records(pxdoc);
    pxfield_t *fields = PX_get_fields(pxdoc);

    for (int rec = 0; rec < num_records; ++rec) {
        pxval_t **pxval;
        pxval = PX_retrieve_record(pxdoc, rec);

        // Both the name and picturefile fields are char(x) fields
        char *name;
        name = pxval[fi_name]->value.str.val;
        char *picturefile;
        picturefile = pxval[fi_picturefile]->value.str.val;

        if (NULL != picturefile) {
            printf("Rec %03d: %s, %s\n", rec, name, picturefile);

            // Test update
            if (tolower(picturefile[0]) == 'z' && picturefile[1] == ':') {
                char *ptr = strrchr(picturefile, '\\');
                char *basename = strdup(ptr + 1);
                int flen = fields[fi_picturefile].px_flen;
                memset(picturefile, 0, flen);
                snprintf(picturefile, flen-1, "Q:\\newpics\\%s", basename);
                free(basename);

                pxval[fi_picturefile]->value.str.len = strlen(picturefile);
                PX_update_record(pxdoc, pxval, rec);
                printf("*** UPDATED: %s\n", picturefile);
            }

            free(picturefile);
        }
    }

    PX_close(pxdoc);
    PX_delete(pxdoc);
}

int main(int argc, char *argv[])
{
    PX_boot();

    for (int i = 1; i < argc; ++i) {
        update_db(argv[i]);
    }

    PX_shutdown();

    return 0;
}
