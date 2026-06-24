#!/bin/bash

# Function to detect package manager
detect_package_manager() {
    if command -v pacman &> /dev/null; then
        echo "pacman"
    elif command -v apt &> /dev/null; then
        echo "apt"
    elif command -v dnf &> /dev/null; then
        echo "dnf"
    elif command -v zypper &> /dev/null; then
        echo "zypper"
    else
        echo "unknown"
    fi
}

# check for the distro
if [ -f /etc/os-release ]; then
    . /etc/os-release
    distro=$ID_LIKE

    # Some distros like Fedora doesn't have "ID_LIKE" in their /etc/os-release file, sadly
    if [ -z "$distro" ]; then
        distro=$ID
    fi
fi

case $distro in
  # Now Vantage can be installed on Cachy OS, ArcoLinux... you name it!
  "arch")
    echo "Installing on Arch Linux or derivative"
    pacman -Qi python-gobject libayatana-appindicator gtk4 libadwaita polkit networkmanager &> /dev/null || sudo pacman -S python-gobject libayatana-appindicator gtk4 libadwaita polkit networkmanager
    ;;

  # Now Vantage can not only be installed on Ubuntu or POP OS but also Kubuntu, KDE Neon, Xubuntu...
  "debian")
    echo "Installing on Debian or derivative"
    dpkg -s python3-gi gir1.2-ayatanaappindicator3-0.1 gir1.2-gtk-4.0 gir1.2-adw-1 libadwaita-1-0 policykit-1 &> /dev/null || sudo apt install python3-gi gir1.2-ayatanaappindicator3-0.1 gir1.2-gtk-4.0 gir1.2-adw-1 libadwaita-1-0 policykit-1
    ;;
  
  # Entry for Linux Mint 21.3 Edge
  "ubuntu debian")
    echo "Installing on Linux Mint Edge"
    dpkg -s python3-gi gir1.2-ayatanaappindicator3-0.1 gir1.2-gtk-4.0 gir1.2-adw-1 libadwaita-1-0 policykit-1 &> /dev/null || sudo apt install python3-gi gir1.2-ayatanaappindicator3-0.1 gir1.2-gtk-4.0 gir1.2-adw-1 libadwaita-1-0 policykit-1
    ;;  

  "fedora")
    echo "Installing on Fedora"
    rpm -q python3-gobject libayatana-appindicator-gtk3 gtk4 libadwaita polkit NetworkManager pipewire-pulseaudio &> /dev/null || sudo dnf install python3-gobject libayatana-appindicator-gtk3 gtk4 libadwaita polkit NetworkManager pipewire-pulseaudio
    ;;

  "opensuse-tumbleweed")
    echo "Installing on OpenSuse"
    rpm -q python3-gobject libayatana-appindicator-gtk3 gtk4 libadwaita polkit NetworkManager pipewire-pulseaudio &> /dev/null || sudo zypper install python3-gobject libayatana-appindicator3-1 typelib-1_0-AyatanaAppIndicator3-0_1 gtk4 libadwaita typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1 polkit NetworkManager pipewire-pulseaudio
    ;;

  *)
    echo "Unknown Distro, attempting package manager detection..."
    package_manager=$(detect_package_manager)
    
    case $package_manager in
        "pacman")
            echo "Detected pacman package manager"
            pacman -Qi python-gobject libayatana-appindicator gtk4 libadwaita polkit networkmanager &> /dev/null || sudo pacman -S python-gobject libayatana-appindicator gtk4 libadwaita polkit networkmanager
            ;;
        "apt")
            echo "Detected apt package manager"
            dpkg -s python3-gi gir1.2-ayatanaappindicator3-0.1 gir1.2-gtk-4.0 gir1.2-adw-1 libadwaita-1-0 policykit-1 &> /dev/null || sudo apt install python3-gi gir1.2-ayatanaappindicator3-0.1 gir1.2-gtk-4.0 gir1.2-adw-1 libadwaita-1-0 policykit-1
            ;;
        "dnf")
            echo "Detected dnf package manager"
            rpm -q python3-gobject libayatana-appindicator-gtk3 gtk4 libadwaita polkit NetworkManager pipewire-pulseaudio &> /dev/null || sudo dnf install python3-gobject libayatana-appindicator-gtk3 gtk4 libadwaita polkit NetworkManager pipewire-pulseaudio
            ;;
        "zypper")
            echo "Detected zypper package manager"
            rpm -q python3-gobject libayatana-appindicator-gtk3 gtk4 libadwaita polkit NetworkManager pipewire-pulseaudio &> /dev/null || sudo zypper install python3-gobject libayatana-appindicator3-1 typelib-1_0-AyatanaAppIndicator3-0_1 gtk4 libadwaita typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1 polkit NetworkManager pipewire-pulseaudio
            ;;
        *)
            echo "Unable to detect compatible package manager, exiting."
            exit 1
            ;;
    esac
    ;;
esac

echo "Requirements are installed"
