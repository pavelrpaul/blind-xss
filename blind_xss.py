from burp import IBurpExtender, IScannerCheck
from burp import ITab
from burp import IHttpListener
from burp import IInterceptedProxyMessage
from burp import IMessageEditorController
from burp import IContextMenuFactory, IContextMenuInvocation
from javax.swing import (JLabel, JTextField, JOptionPane,
    JTabbedPane, JPanel, JButton, JMenu, JMenuItem, JTable, JScrollPane,
    JCheckBox, BorderFactory, Box, JFileChooser)
from javax.swing.border import EmptyBorder
from java.awt import (GridBagLayout, Dimension, GridBagConstraints,
    Color, FlowLayout, BorderLayout, Insets)
from java.net import URL
from javax import swing
from javax.swing.filechooser import FileNameExtensionFilter
from javax.swing.table import AbstractTableModel, DefaultTableModel
from javax.swing.event import TableModelEvent, TableModelListener
from StringIO import StringIO
import os
import re
import threading
import random
from java.lang import Runnable
from java.util import ArrayList, Arrays
import config


class MyTableModelListener(TableModelListener):
    def __init__(self, table, burp, data_dict, file):
        self.table = table
        self.burp = burp
        self.data_dict = data_dict
        self.file = file

    def tableChanged(self, e):
        # print(e.getColumn())
        # print(e.getType())
        if e.getType() == 1:
            data = self.table.getDataVector()
            value = data[-1][1]
            newData = data[-1][0]
            if newData == '':
                return
            if newData[-1] == '\n':
                newData = newData[:-1]
            self.data_dict[newData] = value
            # self.burp.saveToFileAsync(config.Payloads, {data[-1][0] : value}, True)
        if e.getType() == 0:
            for x in self.table.getDataVector():
                key = x[0]
                val = x[1]
                if key == '':
                    continue
                if key[-1] == '\n':
                    key = key[:-1]
                self.data_dict[key] = val
            try:
                self.data_dict.pop('')
            except Exception:
                pass
            self.burp.saveToFileAsync(self.file, self.data_dict)
        if e.getType() == -1:
            # print('-1-1-1-1-1')
            return
        try:
            self.data_dict.pop('')
        except Exception:
            pass


class PyRunnable(Runnable):
    """This class is used to wrap a python callable object into a Java Runnable that is 
       suitable to be passed to various Java methods that perform callbacks.
    """
    def __init__(self, target, *args, **kwargs):
        """Creates a PyRunnable.
           target - The callable object that will be called when this is run.
           *args - Variable positional arguments
           **wkargs - Variable keywoard arguments.
        """
        self.target = target
        self.args = args
        self.kwargs = kwargs
    
    def run(self):
        self.target(*self.args, **self.kwargs)


class BurpExtender(IBurpExtender, ITab, IHttpListener, IMessageEditorController, AbstractTableModel, IContextMenuFactory, IScannerCheck):
    name = "Femida XSS"
    _jTabbedPane = JTabbedPane()
    _jPanel = JPanel()
    _jAboutPanel = JPanel()
    _jPanelConstraints = GridBagConstraints()
    _jLabelParameters = None
    _jTextFieldParameters = None
    _jLabelTechniques = None
    _jTextFieldURL = None
    _jLabelFuzzFactor = None
    _jTextFieldFuzzFactor = None
    _jLabelAdditionalCmdLine = None
    _jTextFieldAdditionalCmdLine = None
    _jButtonSetCommandLine = None
    _jLabelAbout = None
    _overwriteHeader = False
    _overwriteParam = False


    def doActiveScan(self, baseRequestResponse, insertionPoint):
        scan_issues = []
        try:
            requestString = str(baseRequestResponse.getRequest().tostring())
            newRequestString = self.prepareRequest(requestString)

            vulnerable, verifyingRequestResponse = self.quickCheckScan(newRequestString, baseRequestResponse)

        except Exception as msg:
            print(msg)

        return []


    def quickCheckScan(self, preparedRequest, requestResponse):
        check = self._callbacks.makeHttpRequest(requestResponse.getHttpService(), preparedRequest)
        vulner = self._helpers.analyzeResponse(check.getResponse()).getStatusCode() == 200
        return vulner, check


    #
    # implement IBurpExtender
    #
    def registerExtenderCallbacks(self, callbacks):
        self._callbacks = callbacks
        self._helpers = callbacks.getHelpers()
        self._callbacks.setExtensionName(self.name)
        self._callbacks.registerScannerCheck(self)

        self._dictPayloads = {}
        self._dictHeaders = {}
        self._dictParams = {}
        self.status_flag = False
        self.match_row_data = [{}, {}, {}]

        self.jfc = JFileChooser("./")
        self.jfc.setDialogTitle("Upload Payloads")
        self.jfc.setFileFilter(FileNameExtensionFilter("TXT file", ["txt"]))

        self._layout = GridBagLayout()
        self._jPanel.setLayout(self._layout)

        self._jLabelTechniques = JLabel("Press to start:")
        self.createAnyView(self._jLabelTechniques, 0, 0, 3, 1, Insets(0, 0, 10, 0))

        self.submitSearchButton = swing.JButton('Run proxy', actionPerformed=self.active_flag)
        self.submitSearchButton.setBackground(Color.WHITE)
        self.createAnyView(self.submitSearchButton, 3, 0, 6, 1, Insets(0, 0, 10, 0))

        self._jPanel.setBounds(0, 0, 1000, 1000)
        self._jLabelTechniques = JLabel("Your URL (my.burpcollaborator.net):")
        self.createAnyView(self._jLabelTechniques, 0, 1, 3, 1, Insets(0, 0, 10, 0))

        self._jTextFieldURL = JTextField("", 30)
        self.createAnyView(self._jTextFieldURL, 3, 1, 6, 1, Insets(0, 0, 10, 0))

        self._tableModelPayloads = DefaultTableModel() 
        self._tableModelPayloads.addColumn("Payload")
        self._tableModelPayloads.addColumn("Using")

        self._tableModelHeaders = DefaultTableModel() 
        self._tableModelHeaders.addColumn("Header")
        self._tableModelHeaders.addColumn("Using")

        self._tableModelParams = DefaultTableModel() 
        self._tableModelParams.addColumn("Parameter")
        self._tableModelParams.addColumn("Using")

        self._payloadTable = self.createAnyTable(self._tableModelPayloads, 1, Dimension(300, 200))
        self.createAnyView(self._payloadTable, 0, 2, 3, 1, Insets(0, 0, 0, 10))

        self._headerTable = self.createAnyTable(self._tableModelHeaders, 2, Dimension(300, 200))
        self.createAnyView(self._headerTable, 3, 2, 3, 1, Insets(0, 0, 0, 10))

        self._paramTable = self.createAnyTable(self._tableModelParams, 3, Dimension(300, 200))
        self.createAnyView(self._paramTable, 6, 2, 3, 1, Insets(0, 0, 0, 0))

        deletePayloadButton = swing.JButton('Delete',actionPerformed=self.deleteToPayload)
        deletePayloadButton.setBackground(Color.WHITE)
        self.createAnyView(deletePayloadButton, 0, 3, 1, 1, Insets(3, 0, 0, 0))

        deletePayloadButton = swing.JButton('Upload',actionPerformed=self.uploadToPayload)
        deletePayloadButton.setBackground(Color.WHITE)
        self.createAnyView(deletePayloadButton, 1, 3, 1, 1, Insets(3, 0, 0, 0))

        addPayloadButton = swing.JButton('Add',actionPerformed=self.addToPayload)
        addPayloadButton.setBackground(Color.WHITE)
        self.createAnyView(addPayloadButton, 2, 3, 1, 1, Insets(3, 0, 0, 10))

        deleteHeaderButton = swing.JButton('Delete',actionPerformed=self.deleteToHeader)
        deleteHeaderButton.setBackground(Color.WHITE)
        self.createAnyView(deleteHeaderButton, 3, 3, 1, 1, Insets(3, 0, 0, 0))

        self._overwriteHeaderButton = swing.JButton('Overwrite',actionPerformed=self.overwriteHeader)
        self._overwriteHeaderButton.setBackground(Color.WHITE)
        self.createAnyView(self._overwriteHeaderButton, 4, 3, 1, 1, Insets(3, 0, 0, 0))

        addHeaderButton = swing.JButton('Add',actionPerformed=self.addToHeader)
        addHeaderButton.setBackground(Color.WHITE)
        self.createAnyView(addHeaderButton, 5, 3, 1, 1, Insets(3, 0, 0, 10))

        deleteParamsButton = swing.JButton('Delete',actionPerformed=self.deleteToParams)
        deleteParamsButton.setBackground(Color.WHITE)
        self.createAnyView(deleteParamsButton, 6, 3, 1, 1, Insets(3, 0, 0, 0))

        self._overwriteParamButton = swing.JButton('Overwrite',actionPerformed=self.overwriteParam)
        self._overwriteParamButton.setBackground(Color.WHITE)
        self.createAnyView(self._overwriteParamButton, 7, 3, 1, 1, Insets(3, 0, 0, 0))

        addParamsButton = swing.JButton('Add',actionPerformed=self.addToParams)
        addParamsButton.setBackground(Color.WHITE)
        self.createAnyView(addParamsButton, 8, 3, 1, 1, Insets(3, 0, 0, 0))
        
        self._resultsTextArea = swing.JTextArea()
        resultsOutput = swing.JScrollPane(self._resultsTextArea)
        resultsOutput.setMinimumSize(Dimension(800,200))
        self.createAnyView(resultsOutput, 0, 4, 9, 1, Insets(10, 0, 0, 0))

        self.clearSearchButton = swing.JButton('Clear Search Output',actionPerformed=self.clearOutput)
        self.createAnyView(self.clearSearchButton, 3, 6, 3, 1, Insets(3, 0, 0, 0))

        self._callbacks.customizeUiComponent(self._jPanel)
        self._callbacks.addSuiteTab(self)
        self.starterPack()

        self._callbacks.registerHttpListener(self)
        self._callbacks.registerContextMenuFactory(self)

        return


    def createAnyTable(self, table_model, table_number, min_size):
        _table = JTable(table_model)
        _table.setAutoResizeMode(JTable.AUTO_RESIZE_ALL_COLUMNS)
        _scrolltable = JScrollPane(_table)
        _scrolltable.setMinimumSize(min_size)
        return _scrolltable


    def insertAnyTable(self, table, data):
        def detectTable(table):
            table.getColumnName(0)

        new_data = [str(x) for x in data]
        # print('was ', str(table.getRowCount()))
        table.insertRow(table.getRowCount(), new_data)
        # self.match_row_data[tableNum]
        # print('become ', str(table.getRowCount()))
        return table.getRowCount()


    def createAnyView(self, _component, gridx, gridy, gridwidth, gridheight, insets):
        self._jPanelConstraints.fill = GridBagConstraints.HORIZONTAL
        self._jPanelConstraints.gridx = gridx
        self._jPanelConstraints.gridy = gridy
        self._jPanelConstraints.gridwidth = gridwidth
        self._jPanelConstraints.gridheight = gridheight
        self._jPanelConstraints.insets = insets
        self._jPanel.add(_component, self._jPanelConstraints)

    def createMenuItems(self, contextMenuInvocation):
        context = contextMenuInvocation.getInvocationContext()
        filterMenu = JMenu("Femida XSS")
        self._contextMenuData = contextMenuInvocation
        if (context == 0 or context == 1 or
            context == 2 or context == 3):
            filterMenu.add(JMenuItem("Add to Headers", actionPerformed = self.addToHeadersItem))
            filterMenu.add(JMenuItem("Add to Parameters", actionPerformed = self.addToParametersItem))

        return Arrays.asList(filterMenu)

    def addToHeadersItem(self, event):
        start, end = self._contextMenuData.getSelectionBounds()
        message = self._contextMenuData.getSelectedMessages()[0]
        ctx = self._contextMenuData.getInvocationContext()

        if ctx == 0 or ctx == 2:
            message = message.getRequest()
        elif ctx == 1 or ctx == 3:
            message = message.getResponse()
        else:
            print(ctx)
            return
        try:
            selected_text = self._helpers.bytesToString(message)[start:end]
            self.insertAnyTable(self._tableModelHeaders, [str(selected_text), '1'])
        except Exception:
            pass

    def addToParametersItem(self, event):
        start, end = self._contextMenuData.getSelectionBounds()
        message = self._contextMenuData.getSelectedMessages()[0]
        ctx = self._contextMenuData.getInvocationContext()

        if ctx == 0 or ctx == 2:
            message = message.getRequest()
        elif ctx == 1 or ctx == 3:
            message = message.getResponse()
        else:
            print(ctx)
            return
        try:
            selected_text = self._helpers.bytesToString(message)[start:end]
            self.insertAnyTable(self._tableModelParams, [str(selected_text), '1'])
        except Exception:
            pass


    def starterPack(self):
        self.addFromFileAsync(config.Payloads, self._tableModelPayloads)
        self.addFromFileAsync(config.Headers, self._tableModelHeaders)
        self.addFromFileAsync(config.Parameters, self._tableModelParams)
        self._tableModelPayloads.addTableModelListener(MyTableModelListener(self._tableModelPayloads, self, self._dictPayloads, config.Payloads))
        self._tableModelHeaders.addTableModelListener(MyTableModelListener(self._tableModelHeaders, self, self._dictHeaders, config.Headers))
        self._tableModelParams.addTableModelListener(MyTableModelListener(self._tableModelParams, self, self._dictParams, config.Parameters))


    def addToPayload(self, button):
        self.insertAnyTable(self._tableModelPayloads, ['', '1'])

    def addToHeader(self, button):
        self.insertAnyTable(self._tableModelHeaders, ['', '1'])

    def addToParams(self, button):
        self.insertAnyTable(self._tableModelParams, ['', '1'])


    def uploadToPayload(self, button):
        self._returnFileChooser = self.jfc.showDialog(None, "Open")
        if (self._returnFileChooser == JFileChooser.APPROVE_OPTION):
            selectedFile = self.jfc.getSelectedFile()
            self.fileUpload(selectedFile, self._tableModelPayloads)

    def deleteToPayload(self, button):
        try:
            print(str(dir(self._tableModelPayloads)))
            print(str(self._tableModelPayloads.getColumnName(0)))
            # rows = self._payloadTable.getSelectedRows()
            # for i in rows:
            #     self._tableModelPayloads.removeRow(table.getSelectedRow())
            data = self._tableModelPayloads.getDataVector()
            self._dictPayloads.pop(data[-1][0])
            self._tableModelPayloads.removeRow(self._tableModelPayloads.getRowCount()-1)
        except Exception as msg:
            print(msg)
            pass

    def deleteToHeader(self, button):
        try:
            data = self._tableModelHeaders.getDataVector()
            print(data[-1][0])
            self._dictHeaders.pop(data[-1][0])
            self._tableModelHeaders.removeRow(self._tableModelHeaders.getRowCount()-1)
        except Exception as msg:
            print(msg)
            pass

    def deleteToParams(self, button):
        try:
            data = self._tableModelParams.getDataVector()
            print(data[-1][0])
            self._dictParams.pop(data[-1][0])
            self._tableModelParams.removeRow(self._tableModelParams.getRowCount()-1)
        except Exception as msg:
            print(msg)
            pass

    def clearOutput(self, button):
        self._resultsTextArea.setText("")

    def fileUpload(self, path, table):
        with open(str(path), "r") as f:
            for line in f:
                self.insertAnyTable(table, [str(line), '1'])


    def active_flag(self, button):
        if not self.status_flag:
            self.status_flag = True
            self.submitSearchButton.setBackground(Color.GRAY)
            self.appendToResults("Proxy start...")
            self.appendToResults(str(self._dictPayloads))
            self.appendToResults(str(self._dictHeaders))
            self.appendToResults(str(self._dictParams))

        elif self.status_flag:
            self.status_flag = False
            self.submitSearchButton.setBackground(Color.WHITE)
            self.appendToResults("Proxy stop...")


    def overwriteHeader(self, button):
        if not self._overwriteHeader:
            self._overwriteHeader = True
            self._overwriteHeaderButton.setBackground(Color.GRAY)

        elif self._overwriteHeader:
            self._overwriteHeader = False
            self._overwriteHeaderButton.setBackground(Color.WHITE)

    def overwriteParam(self, button):
        if not self._overwriteParam:
            self._overwriteParam = True
            self._overwriteParamButton.setBackground(Color.GRAY)

        elif self._overwriteParam:
            self._overwriteParam = False
            self._overwriteParamButton.setBackground(Color.WHITE)


    def prepareRequest(self, requestString):
        try:
            listHeader = re.findall('([\w-]+):\s?(.*)', requestString)
            dictRealHeaders = {x[0].lower():x[1] for x in listHeader}

            for index, key in enumerate(self._dictHeaders):
                if key.lower() in dictRealHeaders.keys() and self._dictHeaders[key] == '1':
                    if len(self._dictPayloads.keys()) == 0:
                        pass
                    elif self._overwriteHeader:
                        payload = random.choice(self._dictPayloads.keys())
                        payload = payload.replace(r"${URL}$", self._jTextFieldURL.text, 1)
                        requestString = requestString.replace(dictRealHeaders.get(key.lower()), payload, 1)
                    elif not self._overwriteHeader:
                        payload = random.choice(self._dictPayloads.keys())
                        payload = payload.replace(r"${URL}$", self._jTextFieldURL.text, 1)
                        payload = dictRealHeaders.get(key.lower()) + payload
                        requestString = requestString.replace(dictRealHeaders.get(key.lower()), payload, 1)
                else:
                    pass

            listParam = re.findall('[\?|\&]([^=]+)\=([^& ])+', requestString)
            dictRealParams = {x[0].lower():x[1] for x in listParam}
            url = requestString.split(" HTTP/1.")
            for index, key in enumerate(self._dictParams):
                if key.lower() in dictRealParams.keys() and self._dictParams[key] == '1':
                    if len(self._dictPayloads.keys()) == 0:
                        pass
                    elif self._overwriteParam:
                        payload = random.choice(self._dictPayloads.keys())
                        payload = payload.replace(r"${URL}$", self._jTextFieldURL.text, 1)
                        url[0] = url[0].replace(dictRealParams.get(key.lower()), payload, 1)
                    elif not self._overwriteParam:
                        payload = random.choice(self._dictPayloads.keys())
                        payload = payload.replace(r"${URL}$", self._jTextFieldURL.text, 1)
                        payload = dictRealParams.get(key.lower()) + payload
                        url[0] = url[0].replace(dictRealParams.get(key.lower()), payload, 1)
                else:
                    pass
        except Exception as msg:
            print('AAAAAAA ',str(msg))

        return "{} HTTP/1.{}".format(url[0], url[1])


    def processHttpMessage(self, toolFlag, messageIsRequest, messageInfo):
        try:
            if not self.status_flag:
                return
            # only process requests
            if not messageIsRequest:
                return
            requestString = messageInfo.getRequest().tostring()
            newRequestString = self.prepareRequest(requestString)

            self.appendToResults(newRequestString.encode())
            messageInfo.setRequest(newRequestString.encode())
        except Exception as msg:
            self.appendToResults(str(msg))

        
    # Fnction to provide output to GUI
    def appendToResults(self, s):
        """Appends results to the resultsTextArea in a thread safe mannor. Results will be
           appended in the order that this function is called.
        """
        def appendToResults_run(s):  
            self._resultsTextArea.append(s)
            self._resultsTextArea.append('\n')

        swing.SwingUtilities.invokeLater(PyRunnable(appendToResults_run, str(s)))


    def addFromFileAsync(self, file, table):        
        def addFromFile_run(file, table):
           if os.path.exists(file):
                with open(file, 'r') as f:
                    for row in f.readlines():
                        if row != '':
                            temp = row[:-1] if row[-1] == '\n' else row
                            self.insertAnyTable(table, [str(temp), '1'])

        swing.SwingUtilities.invokeLater(PyRunnable(addFromFile_run, file, table))

    def saveToFileAsync(self, file, data, isAppend=False):
        def saveToFile_run(file, data, isAppend):
            # isAppend = 'a' if isAppend is True else 'w'
            isAppend = 'w'
            # print(isAppend)
            with open(file, isAppend) as f:
                for i, k in enumerate(data):
                    f.write("{}\n".format(k))
                    # print("QQQQ{}\nQQQ".format(k))
                f.seek(-1, os.SEEK_END)
                f.truncate()

        swing.SwingUtilities.invokeLater(PyRunnable(saveToFile_run, file, data, isAppend))

    def getTabCaption(self):
        return self.name

    def getUiComponent(self):
        return self._jPanel
