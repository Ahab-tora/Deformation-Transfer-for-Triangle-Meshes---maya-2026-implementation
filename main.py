#--- Imports ---#
import importlib,json
from shiboken6 import wrapInstance
import maya.cmds as cmds
import maya.api.OpenMaya as om
from maya import OpenMayaUI
import maya.mel as mel
from PySide6.QtWidgets import QWidget,QGroupBox,QPushButton,QVBoxLayout,QHBoxLayout,QLabel,QTabWidget,QTextEdit,QLineEdit,QTableWidget,QTableWidgetItem

from PySide6 import QtCore,QtWidgets

from pathlib import Path
from functools import partial

#from test2 import *
from . import core
importlib.reload(core)

def maya_main_window():
	main_window_ptr=OpenMayaUI.MQtUtil.mainWindow()
	return wrapInstance(int(main_window_ptr), QWidget)
        

def selection_formatting(selection:str)-> list[str, int]: 
    '''Formats the selection to a string mesh, and a int index. Ex: 'pSphere1.vtx[12]' -> ['pSphere1', 12]  '''
    mesh, index_brackets = selection.replace('vtx','').split('.')
    index = int(index_brackets.replace('[','').replace(']', ''))
    return [mesh, index]


class Deformation_transfer_ui(QWidget):

    def __init__(self, parent = maya_main_window()):
        super(Deformation_transfer_ui, self).__init__(parent)
        
        self.setGeometry(250,500,250,500)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Window)
        self.setWindowTitle("Deformation transfer")

        # parent window to Maya's main window
        self.l= QVBoxLayout()
        self.setLayout(self.l)


        self.meshes_layout = QHBoxLayout()
        self.l.addLayout(self.meshes_layout)

        #--- ---#

        self.source_mesh = None
        self.deformed_mesh = None
        self.target_mesh = None
        self.pairs = []

        #--- ---#

        self.input_meshes_group = QGroupBox()
        self.input_meshes_group_layout = QVBoxLayout()
        self.input_meshes_group.setLayout(self.input_meshes_group_layout)

        self.source_mesh_text = QLabel('No source mesh selected.')
        self.input_meshes_group_layout.addWidget(self.source_mesh_text)
        self.add_source_mesh_button = QPushButton('Add source mesh')
        self.add_source_mesh_button.clicked.connect(partial(self.load_mesh, text=self.source_mesh_text, attribute_name='source_mesh'))
        self.input_meshes_group_layout.addWidget(self.add_source_mesh_button)

        self.deformed_mesh_text = QLabel('No deformed mesh selected.')
        self.input_meshes_group_layout.addWidget(self.deformed_mesh_text)
        self.add_deformed_mesh_button = QPushButton('Add deformed mesh')
        self.add_deformed_mesh_button.clicked.connect(partial(self.load_mesh, text=self.deformed_mesh_text, attribute_name='deformed_mesh'))
        self.input_meshes_group_layout.addWidget(self.add_deformed_mesh_button)

        self.meshes_layout.addWidget(self.input_meshes_group)

        #--- ---#

        self.target_mesh_group = QGroupBox()
        self.target_mesh_group_layout = QVBoxLayout()
        self.target_mesh_group.setLayout(self.target_mesh_group_layout)

        self.target_mesh_text = QLabel('No target mesh selected.')
        self.target_mesh_group_layout.addWidget(self.target_mesh_text)
        self.add_target_mesh_button = QPushButton('Add target mesh')
        self.add_target_mesh_button.clicked.connect(partial(self.load_mesh, text=self.target_mesh_text, attribute_name='target_mesh'))
        self.target_mesh_group_layout.addWidget(self.add_target_mesh_button)

        self.meshes_layout.addWidget(self.target_mesh_group)


        #--- ---#

        self.pairs_group = QGroupBox(title='Source - target pairs')
        self.pairs_group_layout = QVBoxLayout()
        self.pairs_group.setLayout(self.pairs_group_layout)

        self.pairs_table = QTableWidget()
        self.row_index = -1
        #self.pairs_table.setRowCount(2)
        self.pairs_table.setColumnCount(2)
        headerH = ['source vertex id', 'target vertex id']
        self.pairs_table.setHorizontalHeaderLabels(headerH)
        self.pairs_group_layout.addWidget(self.pairs_table)

        self.pairs_buttons_group = QGroupBox()
        self.pairs_buttons_layout = QHBoxLayout()
        self.pairs_buttons_group.setLayout(self.pairs_buttons_layout)

        self.add_pair_button = QPushButton('Add pair')
        self.add_pair_button.clicked.connect(self.add_pair)
        self.pairs_buttons_layout.addWidget(self.add_pair_button)

        self.delete_pair_button = QPushButton('Delete pair')
        self.delete_pair_button.clicked.connect(self.delete_pair)
        self.pairs_buttons_layout.addWidget(self.delete_pair_button)

        '''self.test_button = QPushButton('test')
        self.test_button.clicked.connect(self.test)
        self.pairs_buttons_layout.addWidget(self.test_button)'''

        self.pairs_group_layout.addWidget(self.pairs_buttons_group)

        self.l.addWidget(self.pairs_group)

        #--- ---#

        self.transfer_deformation_button = QPushButton('Transfer deformation')
        self.transfer_deformation_button.clicked.connect(self.transfer_deformation)
        self.l.addWidget(self.transfer_deformation_button)

    #--- ---#

    '''def test(self):
        for pair in data:
            self.add_pair(pair=pair) #used to test stuff'''


    #--- ---#

    def transfer_deformation(self):

        core.transfer_deformation(source_mesh=self.source_mesh, deformed_mesh=self.deformed_mesh, target_mesh=self.target_mesh,
                                    marker_pairs = self.pairs)

    #--- ---#

    def load_mesh(self, text,attribute_name):

        mesh = cmds.ls(sl=True, an=True)[0] 

        if attribute_name == 'deformed_mesh':
            if not self.source_mesh:
                print('Select source mesh first')
                return
            setattr(self, attribute_name, core.Mesh(mesh_name=mesh,
                                                     source_vertices_order=self.source_mesh.vertices_order))
        else:
            setattr(self, attribute_name, core.Mesh(mesh_name=mesh))

        text.setText(mesh)

    #--- ---#

    def add_pair(self):
        'Adds two vertices to the pairs(markers)'
         
        selection = cmds.ls(sl=True, an=True)

        first_vertex = selection[0]
        if not '.vtx' in first_vertex:
            print('Please select vertices')
            return
        first_vertex_mesh,first_vertex_index = selection_formatting(first_vertex)

        second_vertex = selection[1]
        if not '.vtx' in second_vertex:
            print('Please select vertices')
            return
        second_vertex_mesh,second_vertex_index = selection_formatting(second_vertex)


        '''source_vtx_id, target_vtx_id = cmds.ls(sl=True) #new names for source_vtx and source_vertex
        source_vtx_id = int(source_vtx_id.split('[')[1].split(']')[0]) #Maya returns in the format  mesh.vtx[id] but we only want id
        target_vtx_id = int(target_vtx_id.split('[')[1].split(']')[0])'''

        
        #check if meshes are source and target
        if first_vertex_mesh == self.source_mesh.name:
            source_vtx_id = first_vertex_index
        elif first_vertex_mesh == self.target_mesh.name:
            target_vtx_id = first_vertex_index
        else:
            print('First vertex is not in source nor target mesh')
            return
        
        if second_vertex_mesh == self.source_mesh.name:
            source_vtx_id = second_vertex_index
        elif second_vertex_mesh == self.target_mesh.name:
            target_vtx_id = second_vertex_index
        else:
            print('Second vertex is not in source nor target mesh')
            return
        print(source_vtx_id)
        print(self.source_mesh.vertices_id)
        if not source_vtx_id in self.source_mesh.vertices_id:
            print('Selected source vertex in not in the source mesh.')
            return 
        if not target_vtx_id in self.target_mesh.vertices_id:
            print('Selected target vertex in not in the source mesh.')
            return #should not be needed since we have check if the meshes are source and target, but keep it just in case

        #retrieve vertex class with index
        for vertex in self.source_mesh.vertices: 
            if source_vtx_id == vertex.index:
                source_vertex = vertex
                break
                                                    #use sets instead?
        for vertex in self.target_mesh.vertices:
            if target_vtx_id == vertex.index:
                target_vertex = vertex
                break

            


        source_vertex.mesh.MFnMesh.displayColors = True
        source_vertex.mesh.MFnMesh.setVertexColor(om.MColor((1,0,0,1)), source_vertex.index)
        
        target_vertex.mesh.MFnMesh.displayColors = True
        target_vertex.mesh.MFnMesh.setVertexColor(om.MColor((1,0,0,1)), target_vertex.index)

        self.row_index += 1
        self.pairs_table.insertRow(self.row_index)
        self.pairs_table.setItem(self.row_index, 0, QTableWidgetItem(str(source_vertex.index)))
        self.pairs_table.setItem(self.row_index, 1, QTableWidgetItem(str(target_vertex.index)))

        #self.pairs.append([source_vertex, target_vertex])
        self.pairs.append([target_vertex, source_vertex])

    #--- ---#

    def delete_pair(self):
        'Deletes two vertices from the pairs(markers)'
        source_vertex_id = int(self.pairs_table.item(self.pairs_table.currentRow(),0).text())
        target_mesh_id = int(self.pairs_table.item(self.pairs_table.currentRow(),1).text())

        self.source_mesh.MFnMesh.removeVertexColors([int(self.pairs_table.item(self.pairs_table.currentRow(),0).text())])
        self.target_mesh.MFnMesh.removeVertexColors([int(self.pairs_table.item(self.pairs_table.currentRow(),1).text())])

        self.pairs_table.removeRow(self.pairs_table.currentRow())
        self.pairs.remove([self.source_mesh.id_vertices_dict[source_vertex_id], self.target_mesh.id_vertices_dict[target_mesh_id]])
        self.row_index -= 1



def ui():
    win = Deformation_transfer_ui()
    win.show()
    return win