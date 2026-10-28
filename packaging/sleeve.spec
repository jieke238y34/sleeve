Name:           sleeve
Version:        0.1.0
Release:        1%{?dist}
Summary:        Music library, player and sync dashboard
License:        GPL-3.0-or-later
URL:            https://github.com/jieke238y34/sleeve
Source0:        %{url}/archive/v%{version}/sleeve-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  pyproject-rpm-macros
BuildRequires:  desktop-file-utils
BuildRequires:  libappstream-glib

# Fedora names the Qt bindings python3-pyside6; the pip name in pyproject.toml is PySide6.
Requires:       python3-pyside6
Requires:       python3-mutagen
Recommends:     playlist-sync

%description
Sleeve is a desktop front end for the playlist-sync downloader. It browses the
music library, plays it, and runs sorting, genre repair, duplicate
and playlist jobs from one window.

%prep
%autosetup -n sleeve-%{version}

%generate_buildrequires
%pyproject_buildrequires -R

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files sleeve
install -Dm644 packaging/io.github.jieke238y34.Sleeve.desktop \
    %{buildroot}%{_datadir}/applications/io.github.jieke238y34.Sleeve.desktop
install -Dm644 packaging/io.github.jieke238y34.Sleeve.metainfo.xml \
    %{buildroot}%{_metainfodir}/io.github.jieke238y34.Sleeve.metainfo.xml
install -Dm644 sleeve/data/sleeve.svg \
    %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/io.github.jieke238y34.Sleeve.svg

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/io.github.jieke238y34.Sleeve.desktop
appstream-util validate-relax --nonet %{buildroot}%{_metainfodir}/io.github.jieke238y34.Sleeve.metainfo.xml
%pyproject_check_import -e sleeve.app -e sleeve.player -e sleeve.sync

%files -f %{pyproject_files}
%license LICENSE
%doc README.md CHANGELOG.md
%{_bindir}/sleeve
%{_datadir}/applications/io.github.jieke238y34.Sleeve.desktop
%{_metainfodir}/io.github.jieke238y34.Sleeve.metainfo.xml
%{_datadir}/icons/hicolor/scalable/apps/io.github.jieke238y34.Sleeve.svg

%changelog
* Wed Oct 28 2026 jieke238y34 - 0.1.0-1
- Initial package
