import os
import sys
import logging
from pathlib import Path
import shelve
import requests
from threading import Thread
import dearpygui.dearpygui as dpg
from setproctitle import setproctitle
import traceback
import netifaces
import json

# Setup logging
APP_DIR = os.path.join(str(Path.home()), '.tuxcut')
Path(APP_DIR).mkdir(exist_ok=True)
client_log = Path(os.path.join(APP_DIR, 'tuxcut.log'))
client_log.touch(exist_ok=True)
client_log.chmod(0o666)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(APP_DIR, 'tuxcut.log')),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('tuxcut-client')

try:
    logger.info("Starting TuxCut client...")
    
    class TuxCutGUI:
        def __init__(self):
            logger.debug("Initializing TuxCutGUI...")
            self.live_hosts = []
            self._offline_hosts = []
            self._gw = {}
            self._my = {}
            
            # Load aliases
            try:
                with shelve.open(os.path.join(APP_DIR, 'aliases.db')) as aliases:
                    self.aliases = dict(aliases)
                logger.debug("Loaded aliases successfully")
            except Exception as e:
                logger.error(f"Failed to load aliases: {str(e)}")
                self.aliases = {}

            try:
                # Initialize DPG
                logger.debug("Creating DPG context...")
                dpg.create_context()
                
                # Create viewport with a specific theme
                logger.debug("Creating viewport...")
                dpg.create_viewport()
                dpg.set_viewport_title("TuxCut")
                dpg.set_viewport_width(800)
                dpg.set_viewport_height(600)
                dpg.set_viewport_min_width(600)
                dpg.set_viewport_min_height(400)
                
                # Setup theme
                with dpg.theme() as global_theme:
                    with dpg.theme_component(0):
                        dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (32, 32, 32))
                        dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 255, 255))
                        dpg.add_theme_color(dpg.mvThemeCol_Button, (64, 64, 64))
                        dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (96, 96, 96))
                        dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (48, 48, 48))
                
                dpg.bind_theme(global_theme)
                
                # Create primary window
                with dpg.window(label="TuxCut", tag="main_window", no_close=True):
                    # Protection checkbox
                    dpg.add_checkbox(label="Protect My Computer", callback=self.toggle_protection)
                    
                    # Toolbar buttons
                    with dpg.group(horizontal=True):
                        dpg.add_button(label="Refresh", callback=self.on_refresh)
                        dpg.add_button(label="Cut", callback=self.on_cut)
                        dpg.add_button(label="Resume", callback=self.on_resume)
                        dpg.add_spacer(width=10)
                        dpg.add_button(label="Change MAC", callback=self.on_change_mac)
                        dpg.add_button(label="Set Alias", callback=self.on_give_alias)
                        dpg.add_spacer(width=10)
                        dpg.add_button(label="Exit", callback=self.on_exit)

                    dpg.add_spacer(height=5)
                    
                    # Hosts table
                    with dpg.table(tag="hosts_table", header_row=True, resizable=True, 
                                borders_outerH=True, borders_innerV=True, borders_innerH=True,
                                borders_outerV=True):
                        dpg.add_table_column(label="Status", width_fixed=True, init_width_or_weight=50)
                        dpg.add_table_column(label="IP Address", width_fixed=True, init_width_or_weight=120)
                        dpg.add_table_column(label="MAC Address", width_fixed=True, init_width_or_weight=140)
                        dpg.add_table_column(label="Hostname", width_fixed=True, init_width_or_weight=200)
                        dpg.add_table_column(label="Alias")

                    dpg.add_spacer(height=5)
                    
                    # Status bar
                    with dpg.group(horizontal=True):
                        dpg.add_text("Status: ", tag="status_label")
                        dpg.add_text("Ready", tag="status_bar")

                logger.debug("Window created successfully")
                
                # Configure viewport window size
                dpg.set_primary_window("main_window", True)
                
                # Show viewport
                dpg.setup_dearpygui()
                dpg.show_viewport()
                logger.debug("Viewport shown")
                
                # Check server and initialize
                logger.debug("Checking server status...")
                if not self.is_server():
                    logger.error("Server not running")
                    self.show_error("TuxCut Server stopped", 
                                "Use 'systemctl start tuxcutd' then restart the application")
                    sys.exit(1)
                logger.debug("Server is running")

                # Get gateway info
                logger.debug("Getting gateway info...")
                self.get_gw()
                iface = self._gw.get('iface')
                if not iface:
                    logger.error("No network interface found")
                    self.show_error("Error", "No network interface found")
                    sys.exit(1)
                logger.debug(f"Using interface: {iface}")

                self.get_my(iface)
                logger.debug("Network initialization complete")
                self.trigger_thread()
                logger.debug("Initial scan triggered")
                
            except Exception as e:
                logger.error(f"Failed to initialize GUI: {str(e)}")
                logger.error(traceback.format_exc())
                raise

        def set_status(self, msg):
            try:
                dpg.set_value("status_bar", msg)
                logger.debug(f"Status updated: {msg}")
            except Exception as e:
                logger.error(f"Failed to set status: {str(e)}")

        def show_error(self, title, message):
            try:
                logger.error(f"Error dialog: {title} - {message}")
                with dpg.window(label=title, modal=True, show=True, tag="error_modal", 
                            width=300, height=100, pos=[250, 250]):
                    dpg.add_text(message)
                    dpg.add_button(label="OK", callback=lambda: dpg.delete_item("error_modal"),
                                width=280)
            except Exception as e:
                logger.error(f"Failed to show error dialog: {str(e)}")
                print(f"Error: {title} - {message}")  # Fallback to console

        def fill_hosts_view(self, live_hosts):
            # Clear existing rows
            for child in dpg.get_item_children("hosts_table", slot=1):
                dpg.delete_item(child)
            
            for host in live_hosts:
                status = "🔴" if host['ip'] in self._offline_hosts else "🟢"
                alias = self.aliases.get(host['mac'], '')
                
                with dpg.table_row(parent="hosts_table"):
                    dpg.add_text(status)
                    dpg.add_text(host['ip'])
                    dpg.add_text(host['mac'])
                    dpg.add_text(host['hostname'])
                    dpg.add_text(alias)

            self.set_status("Ready")

        def get_selected_host(self):
            for i, row in enumerate(dpg.get_item_children("hosts_table", slot=1)):
                if dpg.is_item_clicked(row):
                    children = dpg.get_item_children(row, slot=1)
                    return {
                        'ip': dpg.get_value(children[1]),
                        'mac': dpg.get_value(children[2]),
                        'hostname': dpg.get_value(children[3])
                    }
            return None

        def on_cut(self):
            host = self.get_selected_host()
            if not host:
                self.set_status("Please select a host to cut")
                return

            res = requests.post('http://127.0.0.1:8013/cut', json=host)
            if res.status_code == 200 and res.json()['status'] == 'success':
                if host['ip'] not in self._offline_hosts:
                    self._offline_hosts.append(host['ip'])
                self.trigger_thread()
                self.set_status(f"{host['ip']} is now offline")

        def on_resume(self):
            host = self.get_selected_host()
            if not host:
                self.set_status("Please select a host to resume")
                return

            res = requests.post('http://127.0.0.1:8013/resume', json=host)
            if res.status_code == 200 and res.json()['status'] == 'success':
                if host['ip'] in self._offline_hosts:
                    self._offline_hosts.remove(host['ip'])
                self.trigger_thread()
                self.set_status(f"{host['ip']} is back online")

        def on_refresh(self):
            self.trigger_thread()

        def on_change_mac(self):
            res = requests.get(f"http://127.0.0.1:8013/change-mac/{self._gw['iface']}")
            if res.status_code == 200:
                status = res.json()['result']['status']
                msg = "MAC Address changed" if status == 'success' else "Couldn't change MAC"
                self.set_status(msg)

        def on_give_alias(self):
            host = self.get_selected_host()
            if not host:
                self.show_error("Error", "Please select a host first")
                return

            def save_alias(sender):
                alias = dpg.get_value("alias_input")
                self.aliases[host['mac']] = alias
                with shelve.open(os.path.join(APP_DIR, 'aliases.db')) as db:
                    db[host['mac']] = alias
                self.trigger_thread()
                dpg.delete_item("alias_modal")

            with dpg.window(label="Set Alias", modal=True, show=True, tag="alias_modal",
                          width=300, height=100, pos=[250, 250]):
                dpg.add_input_text(label="Alias", tag="alias_input", width=280)
                dpg.add_button(label="Save", callback=save_alias, width=280)

        def on_exit(self):
            self.unprotect()
            dpg.destroy_context()
            sys.exit(0)

        def toggle_protection(self, sender):
            if dpg.get_value(sender):
                self.protect()
            else:
                self.unprotect()

        def protect(self):
            try:
                res = requests.post('http://127.0.0.1:8013/protect', data=self._gw)
                if res.status_code == 200 and res.json()['status'] == 'success':
                    self.set_status('Protection Enabled')
            except Exception as e:
                logger.error(str(e), exc_info=True)

        def unprotect(self):
            try:
                res = requests.get('http://127.0.0.1:8013/unprotect')
                if res.status_code == 200 and res.json()['status'] == 'success':
                    self.set_status('Protection Disabled')
            except Exception as e:
                logger.error(str(e), exc_info=True)

        def trigger_thread(self):
            self.set_status('Refreshing hosts list ...')
            Thread(target=self.t_get_hosts).start()

        def t_get_hosts(self):
            try:
                res = requests.get(f"http://127.0.0.1:8013/scan/{self._my['ip']}")
                if res.status_code == 200:
                    self.live_hosts = res.json()['result']['hosts']
                    self.fill_hosts_view(self.live_hosts)
            except Exception as e:
                logger.error(str(e), exc_info=True)

        def is_server(self):
            try:
                res = requests.get('http://127.0.0.1:8013/status')
                return res.status_code == 200 and res.json()['status'] == 'success'
            except:
                logger.error(sys.exc_info()[1], exc_info=True)
                return False

        def get_gw(self):
            try:
                # First try to get from server
                res = requests.get('http://127.0.0.1:8013/gw')
                logger.debug(f"Gateway response: {res.text}")
                
                if res.status_code == 200:
                    data = res.json()
                    if data['status'] == 'success':
                        self._gw = data['gw']
                        logger.debug(f"Got gateway info from server: {json.dumps(self._gw)}")
                        return
                    
                # If server fails, try to detect locally
                logger.debug("Server gateway detection failed, trying local detection...")
                gws = netifaces.gateways()
                logger.debug(f"Available gateways: {json.dumps(gws)}")
                
                # Get default gateway
                default_gw = gws.get('default', {}).get(netifaces.AF_INET)
                if default_gw:
                    gw_ip, iface = default_gw[0], default_gw[1]
                    logger.debug(f"Found default gateway: {gw_ip} on interface {iface}")
                    
                    # Get interface addresses
                    addrs = netifaces.ifaddresses(iface)
                    logger.debug(f"Interface {iface} addresses: {json.dumps(addrs)}")
                    
                    if netifaces.AF_INET in addrs:
                        self._gw = {
                            'ip': gw_ip,
                            'iface': iface,
                            'mac': self.get_mac_address(iface)
                        }
                        logger.debug(f"Using gateway config: {json.dumps(self._gw)}")
                        return
                
                logger.error("No valid network interface found")
                self.show_error('Error', 'No valid network interface found. Please check your network connection.')
                sys.exit(1)
                
            except Exception as e:
                logger.error(f"Error getting gateway info: {str(e)}")
                logger.error(traceback.format_exc())
                self.show_error('Error', f'Failed to get gateway info: {str(e)}')
                sys.exit(1)

        def get_mac_address(self, iface):
            try:
                if netifaces.AF_LINK in netifaces.ifaddresses(iface):
                    return netifaces.ifaddresses(iface)[netifaces.AF_LINK][0]['addr']
                return None
            except Exception as e:
                logger.error(f"Error getting MAC address for {iface}: {str(e)}")
                return None

        def get_my(self, iface):
            try:
                # First try server
                res = requests.get(f'http://127.0.0.1:8013/my/{iface}')
                logger.debug(f"My info response: {res.text}")
                
                if res.status_code == 200:
                    data = res.json()
                    if data['status'] == 'success':
                        self._my = data['my']
                        logger.debug(f"Got my info from server: {json.dumps(self._my)}")
                        return
                
                # If server fails, try local detection
                logger.debug(f"Server my info detection failed, trying local detection...")
                addrs = netifaces.ifaddresses(iface)
                logger.debug(f"Interface {iface} addresses: {json.dumps(addrs)}")
                
                if netifaces.AF_INET in addrs:
                    addr = addrs[netifaces.AF_INET][0]
                    self._my = {
                        'ip': addr['addr'],
                        'mac': self.get_mac_address(iface)
                    }
                    logger.debug(f"Using my config: {json.dumps(self._my)}")
                    return
                    
                logger.error(f"No IPv4 address found for interface {iface}")
                self.show_error('Error', f'No IPv4 address found for interface {iface}')
                sys.exit(1)
                
            except Exception as e:
                logger.error(f"Error getting my info: {str(e)}")
                logger.error(traceback.format_exc())
                self.show_error('Error', f'Failed to get network info: {str(e)}')
                sys.exit(1)

        def run(self):
            logger.info("Starting main loop...")
            try:
                dpg.show_viewport()
                logger.debug("Viewport shown in run()")
                while dpg.is_dearpygui_running():
                    try:
                        dpg.render_dearpygui_frame()
                    except Exception as e:
                        logger.error(f"Error in render frame: {str(e)}")
                        logger.error(traceback.format_exc())
            except Exception as e:
                logger.error(f"Error in main loop: {str(e)}")
                logger.error(traceback.format_exc())
            finally:
                logger.info("Cleaning up...")
                try:
                    dpg.destroy_context()
                except Exception as e:
                    logger.error(f"Error destroying context: {str(e)}")

    if __name__ == '__main__':
        try:
            setproctitle('tuxcut')
            logger.info("Creating application instance...")
            app = TuxCutGUI()
            logger.info("Running application...")
            app.run()
        except KeyboardInterrupt:
            logger.info("Application terminated by user")
            sys.exit(0)
        except Exception as e:
            logger.error(f"Fatal error: {str(e)}")
            logger.error(traceback.format_exc())
            sys.exit(1)

except Exception as e:
    logger.error(f"Fatal error: {str(e)}")
    logger.error(traceback.format_exc())
    sys.exit(1)
