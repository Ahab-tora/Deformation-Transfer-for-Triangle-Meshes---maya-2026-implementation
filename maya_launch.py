import maya.cmds as cmds
import importlib,sys

#use this in maya script editor to launch


scriptPath = '/home/user/Documents/projects'

if not scriptPath in sys.path:
    sys.path.append(scriptPath)
    
    
import deform_transfer
importlib.reload(deform_transfer)
from deform_transfer import main
importlib.reload(main)
main.ui()