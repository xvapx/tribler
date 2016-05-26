import logging
import os
import sys
import traceback

from PyQt5 import uic
from PyQt5.QtCore import Qt, pyqtSignal, QPoint
from PyQt5.QtGui import QIcon
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QMainWindow, QListView, QLineEdit, QApplication, QTreeWidget, QSystemTrayIcon, \
    QTableWidgetItem, QHeaderView, QAction, QFileDialog
from TriblerGUI.TriblerActionMenu import TriblerActionMenu

from TriblerGUI.channel_torrent_list_item import ChannelTorrentListItem
from TriblerGUI.defs import PAGE_SEARCH_RESULTS, PAGE_CHANNEL_CONTENT, PAGE_CHANNEL_COMMENTS, PAGE_CHANNEL_ACTIVITY, \
    PAGE_HOME, PAGE_MY_CHANNEL, PAGE_VIDEO_PLAYER, PAGE_DOWNLOADS, PAGE_SETTINGS, PAGE_SUBSCRIBED_CHANNELS, \
    PAGE_CHANNEL_DETAILS
from TriblerGUI.dialogs.addtorrentdialog import AddTorrentDialog
from TriblerGUI.dialogs.feedbackdialog import FeedbackDialog
from TriblerGUI.event_request_manager import EventRequestManager
from TriblerGUI.home_recommended_item import HomeRecommendedItem
from TriblerGUI.loading_screen import LoadingScreen
from TriblerGUI.tribler_request_manager import TriblerRequestManager


# TODO martijn: temporary solution to convince VLC to find the plugin path
from TriblerGUI.utilities import get_random_color

os.environ['VLC_PLUGIN_PATH'] = '/Applications/VLC.app/Contents/MacOS/plugins'


class TriblerWindow(QMainWindow):

    resize_event = pyqtSignal()

    def on_exception(self, *exc_info):
        self.setHidden(True)

        exception_text = "".join(traceback.format_exception(*exc_info))
        logging.error(exception_text)

        dialog = FeedbackDialog(self, exception_text)
        result = dialog.exec_()

    def __init__(self):
        super(TriblerWindow, self).__init__()

        self.navigation_stack = []

        sys.excepthook = self.on_exception

        uic.loadUi('qt_resources/mainwindow.ui', self)

        # Remove the focus rect on OS X
        [widget.setAttribute(Qt.WA_MacShowFocusRect, 0) for widget in self.findChildren(QLineEdit) +
         self.findChildren(QListView) + self.findChildren(QTreeWidget)]

        self.menu_buttons = [self.left_menu_button_home, self.left_menu_button_my_channel,
                             self.left_menu_button_subscriptions, self.left_menu_button_video_player,
                             self.left_menu_button_settings, self.left_menu_button_downloads]

        self.channel_back_button.clicked.connect(self.on_page_back_clicked)

        self.channel_tab.initialize()
        self.channel_tab.clicked_tab_button.connect(self.on_channel_tab_button_clicked)

        # fetch the variables, needed for the video player port
        self.variables_request_mgr = TriblerRequestManager()
        self.variables_request_mgr.perform_request("variables", self.received_variables)

        self.video_player_page.initialize_player()
        self.search_results_page.initialize_search_results_page()
        self.settings_page.initialize_settings_page()
        self.subscribed_channels_page.initialize()
        self.my_channel_page.initialize_my_channel_page()
        self.downloads_page.initialize_downloads_page()

        self.event_request_manager = EventRequestManager()
        self.event_request_manager.received_search_result_channel.connect(self.search_results_page.received_search_result_channel)
        self.event_request_manager.received_search_result_torrent.connect(self.search_results_page.received_search_result_torrent)

        self.stackedWidget.setCurrentIndex(PAGE_HOME)

        # Create the system tray icon
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = QSystemTrayIcon()
            self.tray_icon.setIcon(QIcon(QPixmap("images/tribler.png")))
            self.tray_icon.show()

        # TODO Martijn: for now, fill the home page with random items
        self.home_page_table_view.setRowCount(3)
        self.home_page_table_view.setColumnCount(3)

        for x in range(0, 3):
            for y in range(0, 3):
                widget_item = HomeRecommendedItem(self)
                self.home_page_table_view.setCellWidget(x, y, widget_item)

        self.hide_left_menu_playlist()

        self.show()

    def received_torrents_in_channel(self, results):
        items = []
        for result in results['torrents']:
            items.append((ChannelTorrentListItem, result))
        self.channel_torrents_list.set_data_items(items)

    def received_variables(self, variables):
        self.video_player_page.video_player_port = variables["variables"]["ports"]["video~port"]

    def on_top_search_button_click(self):
        self.stackedWidget.setCurrentIndex(PAGE_SEARCH_RESULTS)
        self.search_results_page.perform_search(self.top_search_bar.text())
        self.search_request_mgr = TriblerRequestManager()
        self.search_request_mgr.perform_request("search?q=%s" % self.top_search_bar.text(), None)

    def on_add_torrent_button_click(self, pos):
        menu = TriblerActionMenu(self)

        browseFilesAction = QAction('Browse files', self)
        browseDirectoryAction = QAction('Browse directory', self)
        addUrlAction = QAction('Add URL', self)

        browseFilesAction.triggered.connect(self.on_add_torrent_browse_file)
        browseDirectoryAction.triggered.connect(self.on_add_torrent_browse_dir)
        addUrlAction.triggered.connect(self.on_add_torrent_browse_file)

        menu.addAction(browseFilesAction)
        menu.addAction(browseDirectoryAction)
        menu.addAction(addUrlAction)

        menu.exec_(self.mapToGlobal(self.add_torrent_button.pos()))

    def on_add_torrent_browse_file(self):
        dialog = QFileDialog(self)
        dialog.setWindowTitle("Please select the .torrent file(s)")
        dialog.setNameFilters(["Torrent files (*.torrent)"])
        dialog.exec_()

    def on_add_torrent_browse_dir(self):
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.DirectoryOnly)
        dialog.setWindowTitle("Please select the directory containing the .torrent files")
        dialog.exec_()

    def on_top_menu_button_click(self):
        if self.left_menu.isHidden():
            self.left_menu.show()
        else:
            self.left_menu.hide()

    def on_channel_tab_button_clicked(self, button_name):
        if button_name == "channel_content_button":
            self.channel_stacked_widget.setCurrentIndex(PAGE_CHANNEL_CONTENT)
        elif button_name == "channel_comments_button":
            self.channel_stacked_widget.setCurrentIndex(PAGE_CHANNEL_COMMENTS)
        elif button_name == "channel_activity_button":
            self.channel_stacked_widget.setCurrentIndex(PAGE_CHANNEL_ACTIVITY)

    def deselect_all_menu_buttons(self, except_select=None):
        for button in self.menu_buttons:
            if button == except_select:
                continue
            button.setChecked(False)

    def clicked_menu_button_home(self):
        self.deselect_all_menu_buttons(self.left_menu_button_home)
        self.stackedWidget.setCurrentIndex(PAGE_HOME)
        self.navigation_stack = []
        self.hide_left_menu_playlist()

    def clicked_menu_button_my_channel(self):
        self.deselect_all_menu_buttons(self.left_menu_button_my_channel)
        self.stackedWidget.setCurrentIndex(PAGE_MY_CHANNEL)
        self.my_channel_page.load_my_channel_overview()
        self.navigation_stack = []
        self.hide_left_menu_playlist()

    def clicked_menu_button_video_player(self):
        self.deselect_all_menu_buttons(self.left_menu_button_video_player)
        self.stackedWidget.setCurrentIndex(PAGE_VIDEO_PLAYER)
        self.navigation_stack = []
        self.show_left_menu_playlist()

    def clicked_menu_button_downloads(self):
        self.deselect_all_menu_buttons(self.left_menu_button_downloads)
        self.stackedWidget.setCurrentIndex(PAGE_DOWNLOADS)
        self.navigation_stack = []
        self.downloads_page.load_downloads()
        self.hide_left_menu_playlist()

    def clicked_menu_button_settings(self):
        self.deselect_all_menu_buttons(self.left_menu_button_settings)
        self.stackedWidget.setCurrentIndex(PAGE_SETTINGS)
        self.settings_page.load_settings()
        self.navigation_stack = []
        self.hide_left_menu_playlist()

    def clicked_menu_button_subscriptions(self):
        self.deselect_all_menu_buttons(self.left_menu_button_subscriptions)
        self.subscribed_channels_page.load_subscribed_channels()
        self.stackedWidget.setCurrentIndex(PAGE_SUBSCRIBED_CHANNELS)
        self.navigation_stack = []
        self.hide_left_menu_playlist()

    def hide_left_menu_playlist(self):
        self.left_menu_seperator.setHidden(True)
        self.left_menu_playlist_label.setHidden(True)
        self.left_menu_playlist_list.setHidden(True)

    def show_left_menu_playlist(self):
        self.left_menu_seperator.setHidden(False)
        self.left_menu_playlist_label.setHidden(False)
        self.left_menu_playlist_list.setHidden(False)

    def on_channel_item_click(self, channel_list_item):
        channel_info = channel_list_item.data(Qt.UserRole)
        self.get_torents_in_channel_manager = TriblerRequestManager()
        self.get_torents_in_channel_manager.perform_request("channels/discovered/%s/torrents" % channel_info['dispersy_cid'], self.received_torrents_in_channel)
        self.navigation_stack.append(self.stackedWidget.currentIndex())
        self.stackedWidget.setCurrentIndex(PAGE_CHANNEL_DETAILS)

        # initialize the page about a channel
        self.channel_name_label.setText(channel_info['name'])
        self.channel_num_subs_label.setText(str(channel_info['votes']))

    def on_page_back_clicked(self):
        prev_page = self.navigation_stack.pop()
        self.stackedWidget.setCurrentIndex(prev_page)

    def resizeEvent(self, event):
        for i in range(0, 3):
            self.home_page_table_view.setColumnWidth(i, self.home_page_table_view.width() / 3)
            self.home_page_table_view.setRowHeight(i, 200)

        self.resize_event.emit()

app = QApplication(sys.argv)
window = TriblerWindow()
window.setWindowTitle("Tribler")
sys.exit(app.exec_())