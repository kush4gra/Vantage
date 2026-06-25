project('vantage',
  version: '1.0.0',
  license: 'GPL-3.0-or-later',
  meson_version: '>= 0.59.0',
  default_options: ['warning_level=2'],
)

i18n   = import('i18n')
gnome  = import('gnome')
python = import('python')

py = python.find_installation('python3')

# Absolute install paths used to configure the launcher scripts and the polkit
# action. The package is installed under pkgdatadir as the importable
# `vantage` package (…/share/vantage/vantage).
prefix     = get_option('prefix')
bindir     = prefix / get_option('bindir')
datadir    = prefix / get_option('datadir')
localedir  = prefix / get_option('localedir')
pkgdatadir = datadir / meson.project_name()

subdir('data')
subdir('src')
subdir('po')

gnome.post_install(
  glib_compile_schemas: true,
  gtk_update_icon_cache: true,
  update_desktop_database: true,
)
