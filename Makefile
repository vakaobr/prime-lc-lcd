# Install on distributions without a package (Arch, Fedora, ...).
#   sudo make install        sudo make uninstall
PREFIX ?= /usr/local
PYDIR  ?= $(PREFIX)/lib/prime-lc-lcd
UNITDIR ?= /etc/systemd/system
UDEVDIR ?= /etc/udev/rules.d

.PHONY: install uninstall test lint deb

install:
	install -d $(DESTDIR)$(PREFIX)/bin $(DESTDIR)$(UNITDIR)
	install -Dm0644 -t $(DESTDIR)$(PYDIR)/prime_lc_lcd src/prime_lc_lcd/*.py
	printf '#!/bin/sh\nPYTHONPATH=%s exec python3 -m prime_lc_lcd "$$@"\n' $(PYDIR) > $(DESTDIR)$(PREFIX)/bin/prime-lc-lcd
	chmod 0755 $(DESTDIR)$(PREFIX)/bin/prime-lc-lcd
	sed 's|/usr/bin/prime-lc-lcd|$(PREFIX)/bin/prime-lc-lcd|' packaging/systemd/prime-lc-lcd.service > $(DESTDIR)$(UNITDIR)/prime-lc-lcd.service
	install -Dm0644 packaging/udev/70-prime-lc-lcd.rules $(DESTDIR)$(UDEVDIR)/70-prime-lc-lcd.rules
	test -e $(DESTDIR)/etc/default/prime-lc-lcd || install -Dm0644 packaging/default/prime-lc-lcd $(DESTDIR)/etc/default/prime-lc-lcd
	@if [ -z "$(DESTDIR)" ]; then \
		getent group prime-lc-lcd >/dev/null || groupadd --system prime-lc-lcd; \
		getent passwd prime-lc-lcd >/dev/null || useradd --system --gid prime-lc-lcd --no-create-home \
			--home-dir /nonexistent --shell /usr/sbin/nologin prime-lc-lcd; \
		udevadm control --reload && udevadm trigger --subsystem-match=hidraw --action=change; \
		systemctl daemon-reload && systemctl enable --now prime-lc-lcd; \
	fi

uninstall:
	-systemctl disable --now prime-lc-lcd
	rm -f $(DESTDIR)$(UNITDIR)/prime-lc-lcd.service $(DESTDIR)$(UDEVDIR)/70-prime-lc-lcd.rules $(DESTDIR)$(PREFIX)/bin/prime-lc-lcd
	rm -f $(DESTDIR)$(PYDIR)/prime_lc_lcd/*.py $(DESTDIR)$(PYDIR)/prime_lc_lcd/__pycache__/*.pyc
	-rmdir $(DESTDIR)$(PYDIR)/prime_lc_lcd/__pycache__
	-rmdir $(DESTDIR)$(PYDIR)/prime_lc_lcd $(DESTDIR)$(PYDIR)
	-systemctl daemon-reload
	@echo "Left /etc/default/prime-lc-lcd and the prime-lc-lcd user in place."

test:
	python3 -m pytest -q

lint:
	ruff check . && ruff format --check .

deb:
	scripts/build-deb.sh
