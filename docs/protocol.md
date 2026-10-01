# PRIME LC ARGB LCD protocol

Notes on how the host talks to the screen of the ASUS PRIME LC ARGB LCD
all-in-one cooler. The protocol was worked out by studying ASUS's Windows
utility "Prime LC ARGB LCD" 1.0.8.0 for interoperability, then checked
against a real cooler. No ASUS code is included in this project.

## Device

| | |
|---|---|
| USB ID | `0b05:1bbe` "AsusTek Computer Inc PRIME LC LCD" |
| Interface | one HID interface, interrupt IN `0x81` and OUT `0x01`, 64 bytes, 5 ms |
| Report descriptor | vendor page `0xFF00`, 64-byte input and output reports, no report IDs |

On Linux the kernel's `usbhid` driver binds it and exposes `/dev/hidrawN`. When
writing to hidraw, prefix each 64-byte report with a `0x00` byte (the
"unnumbered report" ID), so a write is 65 bytes.

The cooler draws its own dashboard. The host never sends images; it sends
numbers, and the firmware renders them with the selected theme.

## Message format

Every message from the host is one 64-byte report:

```text
2C <cmd> 01 <len> <payload: len bytes> <sum> 00 ... 00
```

- `2C` is a fixed prefix and `01` appears to be a fixed version/flag byte.
- `<len>` is the payload length.
- `<sum>` is the sum of every preceding byte, modulo 256.
- The rest of the report is zero padding.

The cooler answers every message with a 64-byte input report in the same
format, echoing `<cmd>` with a one-byte payload: `01` means accepted.

```text
2C 20 01 01 01 4F    metrics accepted
2C 10 01 01 01 3F    theme switch accepted
```

## Commands

### `0x20` metrics

Payload, 7 bytes:

| offset | meaning |
|---|---|
| 0 | source label: `00` CPU, `01` GPU |
| 1 | temperature, whole degrees C |
| 2 | temperature, tenths |
| 3 | load, whole percent |
| 4 | load, tenths |
| 5 | clock in MHz, high byte |
| 6 | clock in MHz, low byte |

Example, CPU at 34.1 C, 96.8 % load, 2000 MHz:

```text
2C 20 01 07 00 22 01 60 08 07 D0 B6
```

The vendor utility sends one metrics message per second. It uses the
temperature, the total load and the clock of core #0 for the CPU, or the
temperature, the utilisation and the graphics clock for the GPU.

### `0x10` switch theme

Payload `01 01 00`:

```text
2C 10 01 03 01 01 00 42
```

This advances the screen to its next built-in theme; sending it again keeps
cycling. There is no known message to select a theme by number or to read back
the current one, so tools should only send it when the user asks.

## Open questions

- How many themes there are, and whether the choice survives a power cycle.
- What the screen does when the host stops sending for a long time.
- Whether other payload values for `0x10` select a theme directly.

Reports from other owners are welcome; please open an issue.
