# Desktop entry (translatable keys merged from po/).
desktop_file = i18n.merge_file(
        input: 'vantage.desktop.in',
       output: 'vantage.desktop',
         type: 'desktop',
       po_dir: '..' / 'po',
      install: true,
  install_dir: '/usr/share/applications',
)

desktop_validate = find_program('desktop-file-validate', required: false)
if desktop_validate.found()
  test('validate-desktop', desktop_validate,
    args: [desktop_file],
  )
endif

# AppStream metainfo (translatable text merged from po/).
metainfo_file = i18n.merge_file(
        input: 'org.vantage.Vantage.metainfo.xml.in',
       output: 'org.vantage.Vantage.metainfo.xml',
       po_dir: '..' / 'po',
      install: true,
  install_dir: get_option('datadir') / 'metainfo',
)

appstreamcli = find_program('appstreamcli', required: false)
if appstreamcli.found()
  test('validate-metainfo', appstreamcli,
    args: ['validate', '--no-net', '--explain', metainfo_file],
  )
endif

# GSettings schema.
install_data('org.vantage.Vantage.gschema.xml',
  install_dir: get_option('datadir') / 'glib-2.0' / 'schemas',
)

compile_schemas = find_program('glib-compile-schemas', required: false)
if compile_schemas.found()
  test('validate-gschema', compile_schemas,
    args: ['--strict', '--dry-run', meson.current_source_dir()],
  )
endif

# polkit action — exec.path is templated to the real install bindir so it keeps
# matching the helper pkexec runs.
polkit_conf = configuration_data()
polkit_conf.set('BINDIR', bindir)
configure_file(
        input: 'org.vantage.helper.policy.in',
       output: 'org.vantage.helper.policy',
  configuration: polkit_conf,
      install: true,
  install_dir: get_option('datadir') / 'polkit-1' / 'actions',
)

# Light tray icon, served as raw pixels over D-Bus by the SNI tray.
install_data('icon-tray.png', install_dir: pkgdatadir)

subdir('icons')
