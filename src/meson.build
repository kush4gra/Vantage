# Install the Python package under pkgdatadir as the importable `vantage`
# package (…/share/vantage/vantage). The launchers put pkgdatadir on sys.path.
install_subdir('vantage',
  install_dir: pkgdatadir,
  exclude_directories: ['__pycache__'],
)

# Launcher scripts, configured with the interpreter and install paths.
launcher_conf = configuration_data()
launcher_conf.set('PYTHON', py.full_path())
launcher_conf.set('VERSION', meson.project_version())
launcher_conf.set('PKGDATADIR', pkgdatadir)
launcher_conf.set('LOCALEDIR', localedir)

configure_file(
        input: 'vantage.in',
       output: 'vantage',
  configuration: launcher_conf,
      install: true,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x',
)

# Root-owned privileged helper, run via pkexec (gated by the polkit action).
configure_file(
        input: 'vantage-helper.in',
       output: 'vantage-helper',
  configuration: launcher_conf,
      install: true,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x',
)
