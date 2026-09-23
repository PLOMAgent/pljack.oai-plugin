# PL Omarchy ScreenSaver Util

An Omarchy bar widget for editing the screensaver text and idle timeout. Plugin ID: `pljack.oai-plugin`.

The ⱓ button opens a theme-aware panel where you can:

- Enter a single line of text and use **Save & Preview** to generate figlet artwork and preview it immediately.
- Set the automatic screensaver timeout in seconds, with a live approximate minutes conversion. The timeout must be shorter than the configured lock timeout.
- Use **Restore Default** to restore the Omarchy artwork and a 150-second timeout.
- Use **Cancel** to close the panel without changing settings.

When the stock artwork is active, the text field shows “Omarchy.”

## Requirements

Omarchy shell with bar-widget plugin support, Python 3, `figlet` with the `ansi-regular` font, `systemd-run --user`, and the Omarchy screensaver commands. No third-party Python packages are required.

## Install

Install from the public repository:

```sh
omarchy plugin add https://github.com/PLOMAgent/pljack.oai-plugin.git --enable
```

Omarchy clones the repository into `~/.config/omarchy/plugins/pljack.oai-plugin/`. If the bar button does not appear immediately, run `omarchy restart shell`. For an installation originally cloned from this repository, use `omarchy plugin update pljack.oai-plugin` for future updates. An existing manually copied installation is not a Git checkout: back it up and remove it before installing from Git (the plugin-specific text and timeout settings live outside the plugin directory). To remove the Git-installed plugin, use `omarchy plugin remove pljack.oai-plugin`.

Plugins run unsandboxed inside the Omarchy shell; review the source before enabling a repository you do not trust.

## Testing

```sh
python3 -m unittest -v test_screensaver_text.py
omarchy plugin validate .
```

Tests exercise the helper against temporary files without opening a screensaver or changing your live configuration.

## Data and behavior

The helper writes plain text to `~/.config/omarchy/screensaver-text.json`, generated artwork to `~/.config/omarchy/branding/screensaver.txt`, and only the `idle.screensaver` setting in `~/.config/omarchy/shell.json`. A changed timeout schedules a shell restart so the running idle monitor uses it. **Save & Preview** opens the screensaver immediately regardless of the configured automatic timeout.
