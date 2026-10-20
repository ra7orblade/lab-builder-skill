# Platform and emulator facts (validated - reuse instead of re-testing)

Add a dated line whenever a run validates something new. Each entry gives the source and date. Trust these entries: there is no need to re-test them.

## Cisco Modeling Labs (CML 2.10, cml-mcp 0.32 via MCP) - validated 2026-10-19

- **Lab title limit is 64 characters**, description 4096, notes 32768. `labkit.py cml` enforces them.
- **Import with `create_full_lab_topology`.** It takes a JSON *object*, not YAML text. Generate it with `labkit.py cml ... x.json` and pass the parsed object. Schema version `0.2.2` is accepted. Configs go in each node's `configuration` string.
- **`send_cli_command` needs the server started as `uvx --from 'cml-mcp[pyats]' cml-mcp`.** Plain `cml-mcp` lacks pyATS and fails with "PyATS and Genie are required". This change downloads about 1.7 GB, so **ask the user first**. Without it, labs can still be built, but no CLI validation is possible.
- **`configure_cml_node` only works on nodes in the CREATED state** (new or wiped). To change a day-0 config afterwards, wipe the node, which needs user confirmation.
- **`delete_cml_lab` and `wipe_cml_lab` require explicit user confirmation.** Never use them on your own initiative.
- **Day-0 configs reach IOL nodes over TFTP.** `show ip int brief` shows Method `TFTP`, and **`startup-config` stays empty** until someone runs `write memory`. To get a clean rollback point, run `write memory` once on the baseline. After that, `configure replace nvram:startup-config force` restores the baseline in seconds. That is also the learner's reset procedure.
- **Interface lists come from `get_node_definition_detail` (`device.interfaces.physical`).** `assets/cml-nodedefs.json` caches the common ones, so pass `--nodedefs` only for definitions that are not cached.
- `unmanaged_switch` ports are `port0..port31`. Alpine has `eth0..eth3`, with `default_count` 1.
- Licence: check node limits with `get_cml_licensing_details` (CML Free and Personal tiers cap the node count).

## Cisco IOL-XE (`iol-xe`, IOS XE 17.18.2) - validated 2026-10-19

- **Every interface needs IP configuration in the day-0 config, or the router enters the setup dialog on boot.** `labkit.py configs` adds `no ip address` and `shutdown` to unused interfaces.
- **Ethernet defaults are BW 10000 Kbit/s and DLY 1000 µs; loopbacks are BW 8000000 Kbit/s and DLY 5000 µs.** EIGRP classic metric per Ethernet hop: 256 × (1000 + 100·hops).
  - one Ethernet hop to a connected LAN: 281600
  - two hops: 307200
  - three hops: 332800
  - a `delay 300` link adds 200 tens-of-µs compared with a normal link
- **Logging buffer defaults to 4096 bytes.** Have learners set `logging buffered 65536` in Part 1 if they will read syslog history.
- **CDP is on.** The platform string shows `Linux Uni`.
- **`key-string` prints a `SECURITY WARNING ... type 0/7` message.** It is harmless; mention it in Platform Notes.
- **`show ip protocols | section eigrp` cuts off before "Routing for Networks" and "Passive Interface(s)".** Use the full `show ip protocols`, or `| begin Routing Protocol is "eigrp`.
- `clear logging` prints `Error: Failed to set Clear Logging Chasfs Property` but still clears the buffer. Harmless.
- EIGRP syslog matches the Cisco Press text, for example:
  - `%DUAL-5-NBRCHANGE ... is down: K-value mismatch`
  - `%DUAL-6-NBRINFO ... is blocked: not on common subnet (x/y)`

## Alpine Linux host (`alpine`, CML) - validated 2026-10-19

- **The config is a shell script sourced as root at boot.** Use `ip address add A/L dev eth0`, `ip link set dev eth0 up` and `ip route add default via GW`.
- **BusyBox `ping` prints nothing for ICMP unreachables**: it only reports 100% loss. **Use `traceroute -n`**: a missing route shows as `!H` from the gateway, which is the counterpart of Windows' "Reply from <gw>: Destination host unreachable".
