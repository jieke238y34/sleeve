Name:           sleeve
Version:        0.2.0
Release:        1%{?dist}
Summary:        Music player and library manager for the music you own
License:        GPL-3.0-or-later
URL:            https://github.com/jieke238y34/sleeve
Source0:        %{url}/archive/v%{version}/sleeve-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  desktop-file-utils
%if 0%{?suse_version}
# openSUSE: no pyproject-rpm-macros; the plain macros come with python-rpm-macros.
BuildRequires:  python-rpm-macros
BuildRequires:  python3-pip
BuildRequires:  python3-setuptools >= 68
BuildRequires:  python3-wheel
BuildRequires:  appstream-glib
BuildRequires:  fdupes
%else
BuildRequires:  pyproject-rpm-macros
BuildRequires:  libappstream-glib
%endif

# The Qt bindings are python3-pyside6 in both distributions; the pip name in pyproject.toml is PySide6.
Requires:       python3-pyside6
Requires:       python3-mutagen
# Volume above 100% needs pactl; same-volume levelling for files without ReplayGain tags needs ffmpeg.
Recommends:     pulseaudio-utils
Suggests:       ffmpeg
# The optional download front end (dl.py); not packaged by the distributions yet, so only a hint.
Suggests:       playlist-sync

%description
Sleeve is a desktop music player and library manager for the music you own. It has
a library browser with instant search, a tag editor, synced lyrics, playlists, a
Health page for songs that need attention, an Identity page built from your own
listening, and looks that follow the album cover and the seasons. It can show what
is playing on Discord and front the optional playlist-sync downloader. No accounts
and no telemetry: it uses the internet only when you ask.

%prep
%autosetup -n sleeve-%{version}

%if ! 0%{?suse_version}
%generate_buildrequires
%pyproject_buildrequires -R
%endif

%build
%pyproject_wheel

%install
%pyproject_install
%if 0%{?suse_version}
%python_expand %fdupes %{buildroot}%{python3_sitelib}
%else
%pyproject_save_files sleeve
%endif
install -Dm644 packaging/io.github.jieke238y34.Sleeve.desktop \
    %{buildroot}%{_datadir}/applications/io.github.jieke238y34.Sleeve.desktop
install -Dm644 packaging/io.github.jieke238y34.Sleeve.metainfo.xml \
    %{buildroot}%{_datadir}/metainfo/io.github.jieke238y34.Sleeve.metainfo.xml
install -Dm644 sleeve/data/sleeve.svg \
    %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/io.github.jieke238y34.Sleeve.svg

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/io.github.jieke238y34.Sleeve.desktop
appstream-util validate-relax --nonet %{buildroot}%{_datadir}/metainfo/io.github.jieke238y34.Sleeve.metainfo.xml
%if ! 0%{?suse_version}
%pyproject_check_import -e sleeve.app -e sleeve.player -e sleeve.sync
%endif

%if 0%{?suse_version}
%files
%{python3_sitelib}/sleeve
%{python3_sitelib}/sleeve-%{version}.dist-info
%else
%files -f %{pyproject_files}
%endif
%license LICENSE
%doc README.md CHANGELOG.md
%{_bindir}/sleeve
%{_datadir}/applications/io.github.jieke238y34.Sleeve.desktop
%{_datadir}/metainfo/io.github.jieke238y34.Sleeve.metainfo.xml
%{_datadir}/icons/hicolor/scalable/apps/io.github.jieke238y34.Sleeve.svg

%changelog
* Fri Oct 30 2026 jieke238y34 - 0.2.0-1
- New upstream release 0.2.0: seasons and holiday looks, Discord status with album cover, listening history on the
  Identity page, MusicBrainz tag filling on Health, a number-only volume bubble, Settings search
- Builds on openSUSE as well (zypper); optional tools are weak dependencies

* Wed Oct 28 2026 jieke238y34 - 0.1.0-1
- Initial package
