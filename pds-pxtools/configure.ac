#
# pxlib and pxview
#
# Originally written by Uwe Steinmann (see pxlib.sourceforge.net)
#

AC_INIT(pds-pxtools, [0.5], [http://github.com/epiphany40223/epiphany])
AM_INIT_AUTOMAKE([foreign dist-bzip2 no-define 1.14])

AM_SILENT_RULES([yes])

AC_CONFIG_MACRO_DIR([m4])

dnl Checks for programs.
AC_PROG_CC_C99

dnl pxlib
AC_ARG_WITH(pxlib,
    AC_HELP_STRING([--with-pxlib=DIR],
                   [If libpx is in a non-standard directory, specify it here]))

AC_MSG_CHECKING([for pxlib])
AS_IF([test "$with_pxlib" = "no"],
      [AC_MSG_RESULT([no (--without-pxlib specified)])
       AC_MSG_WARN([pxlib support is required; you cannot specify --without-pxlib])
       AC_MSG_ERROR([cannot continue])])

AS_IF([test "$with_pxlib" = "yes"],
      [with_pxlib=])

AS_IF([test "$with_pxlib" != ""],
      [AS_IF([test -d "$with_pxlib/include" && \
              test -d "$with_pxlib/lib"],
             [AC_MSG_RESULT([searching $with_pxlib])
              CPPFLAGS="-I$with_pxlib/include $CPPFLAGS"
              LDFLAGS="-L$with_pxlib/lib $LDFLAGS"],
             [AC_MSG_RESULT([bad value: $with_pxlib])
              AC_MSG_WARN([$with_pxlib/include or $with_pxlib/lib does not exist])
              AC_MSG_ERROR([cannot continue])])
      ],
      [AC_MSG_RESULT([searching default locations])])

HAVE_PXLIB=0
AC_CHECK_HEADER([paradox.h],
    [AC_CHECK_LIB([px], [PX_boot],
         [LIBS="-lpx $LIBS"
          HAVE_PXLIB=1])])

AS_IF([test $HAVE_PXLIB -eq 0],
      [AC_MSG_WARN([pxlib support not found])
       AC_MSG_ERROR([cannot continue])])

dnl Party on
AC_CONFIG_HEADER([config.h])

AC_CONFIG_FILES([
    Makefile

    mem-fam-picturefiles/Makefile
])

AC_OUTPUT
