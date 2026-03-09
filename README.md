Requirements:
Maya 2026 (we are using PySide6 for the ui)
numpy
scipy

Link to the paper:
https://people.csail.mit.edu/sumner/research/deftransfer/Sumner2004DTF.pdf


 #--- How to use ---#
 check the requirements are met
 Download the files and put them in the folder of your choice,
 copy maya_launch.py in the maya script editor, change scriptPath
 Load the meshes, choose markers between source and target, and then you can transfer the deformation
 #--- --- ---#


The idea of the paper is to transfer the deformation of a source mesh to a different target mesh, even if they don't share the same topology or number of vertices, as long as they share a semantic correspondence.
This is has a lot of very useful applications, for exemple for facial rigging, to transfer expressions between characters instead of rebuilding each expression from scratch, or to pose non-rigged meshes.

We need: a source mesh, a deformed (or posed) source mesh, and a target mesh.

We supply a set of markers between the source and the target, for exemple the upper lip of the source and the upper lip of the target. This set of markers enables us to deform the source into the target, once that is done, we can compute a correspondence map between the source and target by comparing the centroids of the triangles and their normals.
This leaves us with an association of triangles, each target triangle has to deform in the same way as a source triangle.

We can then compute the change of shape between the source and deformed meshes for each triangles, as an affine transformation (3x3 matrix) without any displacement vector. Using the correspondence map, we can apply this transformation to each target triangle, by solving a constrained optimization problem to avoid "breaking" the target mesh.
We are left with the target mesh deformed in the same way as the deformed mesh.

This is still a work in progress, and there are still some issues to solve, like performance, and the target mesh getting an offset, but I'm already pretty happy with the results!
