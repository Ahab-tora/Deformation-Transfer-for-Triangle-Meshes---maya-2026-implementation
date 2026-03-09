#--- Imports ---#

import numpy as np

import scipy.linalg as la
from scipy import sparse
from scipy.sparse.linalg import spsolve
from scipy.spatial import KDTree

import pprint
import time

import maya.cmds as cmds
import maya.api.OpenMaya as om

#--- ---#


#--- Classes ---#

class Vertex():

    def __init__(self, mesh, index=None, pos=[]):

        self.index = index
        self.mesh = mesh
        self.triangles = [] #in most cases a vertex shares multiple triangles | change this to set? 

        self._pos = pos
        #cached could be replaced by virtual namewise? Like vertex.virtual_pos instead of vertex.cached_pos
        self.cached_pos = self.pos #used to compute the correspondace map without actually changing the position

    @property
    def normal(self):
        'Returns the normal of the vertex using MFnMesh.getVertexNormal'
        return self.mesh.MFnMesh.getVertexNormal(vertexId = self.index, angleWeighted=False)
        
    @property
    def pos(self): 
        'Returns the local position of a vertex as a list [x, y, z]'
        if self._pos is None or len(self._pos) == 0:
            self._pos = cmds.pointPosition(f'{self.mesh.name}.vtx[{self.index}]',l=True)
        return self._pos
    
    @pos.setter
    def pos(self, value:list):
        'Sets the position for the vertex'
        cmds.xform(f'{self.mesh.name}.vtx[{self.index}]',t=value,os=True)
        self._pos = value

#--- ---#

class Triangle():

    def __init__(self,vertices, mesh, index:int=None, affine_transformation=None):

        self.index = index
        self.vertices = vertices #vertices classes
        self.mesh = mesh
        self.affine_transformation = affine_transformation #3x3 matrix
        self.fourth_vertex = None

        self._adj_triangles = []
        self._normal = []

        self.vertices_index = set()
        for vertex in vertices:
            self.vertices_index.add(vertex.index)
            vertex.triangles.append(self)
        
        self.corresponding_triangle = None #correspondence map, one triangle class of the other mesh

    @property
    def normal(self):
        'Returns the normal of the triangle based on vertices position'
        if len(self._normal) == 0:
            self._normal = np.cross(np.subtract(self.vertices[1].pos, self.vertices[0].pos),
                                    np.subtract(self.vertices[2].pos, self.vertices[0].pos))
        return self._normal

    @property
    def cached_normal(self):
        'Returns the normal of the triangle based on vertices cached position'
        return np.cross(np.subtract(self.vertices[1].cached_pos, self.vertices[0].cached_pos),
                        np.subtract(self.vertices[2].cached_pos, self.vertices[0].cached_pos))

    @property
    def adj_triangles(self) -> list:
        'Return a list of the adjacent triangles, i.e triangles sharing at least two vertices with self'
        if self._adj_triangles: #they don't change, no need to recompute
            return self._adj_triangles

        for triangle in self.mesh.triangles:
            common_vertices_nb = len(set(self.vertices_index).intersection(set(triangle.vertices_index)))
            if common_vertices_nb == 2: #check it there are at least two common vertices
                self._adj_triangles.append(triangle)
        return self._adj_triangles

    @property
    def V(self) -> np.column_stack:
        'Return collection of affine transformations V, 3x3 matrix (np.column_stack)'
        return np.column_stack([
        np.subtract(self.vertices[1].pos, self.vertices[0].pos),
        np.subtract(self.vertices[2].pos, self.vertices[0].pos),
        np.subtract(self.fourth_vertex.pos, self.vertices[0].pos)])
    
    @property
    def V_inv(self):
        'Returns V-¹'
        return np.linalg.inv(self.V)

    @property
    def centroid(self) -> list:
        'Return the centroid of the triangle [x,y,z]'
        x = (self.vertices[0].pos[0] + self.vertices[1].pos[0] + self.vertices[2].pos[0])/3
        y = (self.vertices[0].pos[1] + self.vertices[1].pos[1] + self.vertices[2].pos[1])/3
        z = (self.vertices[0].pos[2] + self.vertices[1].pos[2] + self.vertices[2].pos[2])/3
        return [x,y,z]
    
    @property
    def cached_centroid(self) -> list:
        'Return the centroid of the triangle using the vertices cached position [x,y,z]'
        x = (self.vertices[0].cached_pos[0] + self.vertices[1].cached_pos[0] + self.vertices[2].cached_pos[0])/3
        y = (self.vertices[0].cached_pos[1] + self.vertices[1].cached_pos[1] + self.vertices[2].cached_pos[1])/3
        z = (self.vertices[0].cached_pos[2] + self.vertices[1].cached_pos[2] + self.vertices[2].cached_pos[2])/3
        return [x,y,z]

#--- ---#

class Mesh():

    def __init__(self,mesh_name,source_vertices_order:list=None):

        self.name = mesh_name 

        self.orig_position = cmds.xform(self.name, q=True, t=True, ws=True)

        self.triangles =[] #set instead?
        self.vertices = [] #set instead?

        self.id_vertices_dict = {} #id is key, vertex class is value
        self.id_triangles_dict = {} #id is key, triangle class is value
        
        sel = om.MGlobal.getSelectionListByName(mesh_name)
        dagPath = sel.getDagPath(0)
        self.MFnMesh = om.MFnMesh(dagPath)

        n, vertices = self.MFnMesh.getTriangles() #we need to convert them to list, because this return 2 'OpenMaya.MIntArray'
        n = list(n)  #number of triangle for each polygon
        if source_vertices_order == None:
            self.vertices_order = list(vertices) #ids of all triangles vertices
        else:
            self.vertices_order = source_vertices_order


        self.vertices_id = set(vertices) #get rid of duplicate vertices 

        if not n.count(2)*2 + n.count(1) == sum(n): #in n, there should only 1 and 2, if there is another number -> there is an ngon
            raise SyntaxError('The mesh has ngons.') #Not sure about the kind of error there?

        triangles_index = 0
        for vertex_1, vertex_2, vertex_3 in zip(self.vertices_order[0::3], self.vertices_order[1::3], self.vertices_order[2::3]):

            triangles_vertices = []
            for vertex_index in [vertex_1, vertex_2, vertex_3]:
                if not vertex_index in self.id_vertices_dict:
                    vertex = Vertex(index =vertex_index, mesh = self)
                    self.id_vertices_dict[vertex_index] = vertex

                    self.vertices.append(vertex)
                    triangles_vertices.append(vertex)

                else:
                    triangles_vertices.append(self.id_vertices_dict[vertex_index])

            triangle = Triangle(index = triangles_index, vertices=triangles_vertices, mesh = self)
            self.id_triangles_dict[triangles_index] = triangle
            triangles_index += 1
            self.triangles.append(triangle)

        self.id_vertices_dict = {k: v for k, v in sorted(self.id_vertices_dict.items(), key=lambda item: item[0])} #sort dict by key to match the index of the KDtree we build
        self.id_triangles_dict = {k: v for k, v in sorted(self.id_triangles_dict.items(), key=lambda item: item[0])} #sort dict by key to match the index of the KDtree we build
        
#--- ---#
#--- ---#
#--- ---#

def distance_between(point_1, point_2):
    'Returns the distance between p1 and p2'
    return np.sqrt((point_1[0] - point_2[0])**2 + (point_1[1] - point_2[1])**2 + (point_1[2] - point_2[2])**2 )

#--- ---#

def vector_magnitude(vector):
    'Returns the magnitude of a vector.'
    return np.sqrt(vector[0]**2 + vector[1]**2 + vector[2]**2)

#--- ---#

def angle_between(v1, v2):
    'Returns the angle between vector v1 and vector v2.'
    radians = np.arccos(np.dot(v1,v2)/(vector_magnitude(v1) * vector_magnitude(v2)))
    return radians * 180/np.pi

#--- ---#

def get_vector(point1:list, point2:list):
    "Returns the vector between 2 points"
    vector =(
        point1[0] - point2[0],
        point1[1] - point2[1],
        point1[2] - point2[2]) 
    return vector

#--- ---#

#this works, and is based on the first method (3D method) of "3D Distance from a Point to a Triangle Mark W. Jones Technical Report CSR-5-95"
#However, using the 2D Method could prove more efficient, or even using simpler barycentric coordinates,
#because this looks pretty complicated 
def closest_point_to_triangle(triangle, point:list):

    p1 = np.array(triangle.vertices[0].pos) 
    p2 = np.array(triangle.vertices[1].pos) 
    p3 = np.array(triangle.vertices[2].pos)

    triangle_normal = np.array(triangle.normal)
    point = np.array(point)


    triangle_normal = np.cross(p2-p1 , p3-p1)

    point = np.array(point)

    triangle_point_vector = p1 - point

    triangle_point_vector_magnitude = vector_magnitude(triangle_point_vector)


    angle = np.dot(triangle_normal,triangle_point_vector)/(vector_magnitude(triangle_normal) * vector_magnitude(triangle_point_vector))
    inv_vector_magnitude = triangle_point_vector_magnitude * angle
    


    inv_vector = inv_vector_magnitude * triangle_normal/vector_magnitude(triangle_normal) # negative sign ?

    new_point = point + inv_vector


    p2p1 = get_vector(point1=p2, point2=p1)
    p2p1_magnitude = vector_magnitude(p2p1)

    p3p1 = get_vector(point1=p3, point2=p1)
    p3p1_magnitude = vector_magnitude(p3p1)

    p3p2 = get_vector(point1=p3, point2=p2)
    p3p2_magnitude = vector_magnitude(p3p2)

    p1p2 = get_vector(point1=p1, point2=p2)
    p1p2_magnitude = vector_magnitude(p1p2)

    p1p3 = get_vector(point1=p1, point2=p3)
    p1p3_magnitude = vector_magnitude(p1p3)

    p2p3 = get_vector(point1=p2, point2=p3)
    p2p3_magnitude = vector_magnitude(p2p3)


    v1 = p2p1/p2p1_magnitude + p3p1/p3p1_magnitude
    v2 = p3p2/p3p2_magnitude + p1p2/p1p2_magnitude
    v3 = p1p3/p1p3_magnitude + p2p3/p2p3_magnitude

    f1 = np.dot(np.cross(v1, get_vector(p1, new_point)), triangle_normal)
    f2 = np.dot(np.cross(v2, get_vector(p2, new_point)), triangle_normal)
    f3 = np.dot(np.cross(v3, get_vector(p3, new_point)), triangle_normal)

    new_point_to_p1 = get_vector(point1=new_point, point2=p1)
    new_point_to_p2 = get_vector(point1=new_point, point2=p2)
    new_point_to_p3 = get_vector(point1=new_point, point2=p3)
    
    point_outside = False #if the point is outside of the triangle, it is closer to a side or vertex
    #if fn > 0, the point is anticlockwise to vn
    if f2 < 0 and f1 > 0: #clockwise to v2 and anti to v1
        if np.dot(np.cross(new_point_to_p1, new_point_to_p2), triangle_normal) < 0:
            point_outside = True
    elif f3 < 0 and f2 > 0: #clockwise to v3 and anti to v2
        if np.dot(np.cross(new_point_to_p2, new_point_to_p3), triangle_normal) < 0:
            point_outside = True
    elif f1 < 0 and f3 > 0: #clockwise to v1 and anti to v3
        if np.dot(np.cross(new_point_to_p3, new_point_to_p1), triangle_normal) < 0:
            point_outside = True

    if not point_outside: #if the point is inside the triangle, it means the closest point on triangle is this one
        distance = distance_between(point_1 = new_point, point_2 = point)
        return new_point, distance

    edges_data = [[p1p2, p1, p2], [p2p3, p2, p3], [p3p1, p3, p1]]

    best_point = None
    best_distance = 99999 #find better way than that
    
    for data in edges_data:

        edge = data[0]
        first_point = data[1] #maybe find better names ?
        second_point = data[2]
        
        new_point_to_first_point = get_vector(point1=new_point,point2=first_point)
        new_point_to_second_point = get_vector(point1=new_point,point2=second_point)

        R = np.cross(np.cross(new_point_to_first_point, new_point_to_second_point), edge ) #direction of P'0 to P"0
        R_magnitude = vector_magnitude(R)

        gamma = np.dot(triangle_point_vector, R) / (triangle_point_vector_magnitude * R_magnitude) #this is an angle, better suited name needed

        length = triangle_point_vector_magnitude * np.cos(gamma) #length P'0 P"0

        point_on_line_projection_vector = length * (R/R_magnitude)

        point_on_line_projection = new_point + point_on_line_projection_vector

        edge_vector = second_point - first_point
        t = np.dot(point_on_line_projection - first_point, edge_vector) / np.dot(edge_vector, edge_vector) #?

        if 0 <= t <= 1: #point on line is between p1 p2

            closest_point = first_point + t * edge_vector
            distance = distance_between(point_1=closest_point, point_2 = point)
            if distance < best_distance:
                best_distance = distance
                best_point = closest_point

        elif t < 0: #closest to p1
            distance = distance_between(point_1 = first_point, point_2 = point)
            if distance < best_distance:
                best_distance = distance
                best_point = first_point
        
        elif t > 1: #closest to p2
            distance = distance_between(point_1 = second_point, point_2 = point)
            if distance < best_distance:
                best_distance = distance
                best_point = second_point

    return best_point, best_distance

#--- ---#

def compute_fourth_vertex(triangle) -> Vertex:
    'Returns a vertex helping establishing the space perpendicular to the triangle.'
    edge_1 = np.subtract(triangle.vertices[1].pos, triangle.vertices[0].pos)
    edge_2 = np.subtract(triangle.vertices[2].pos, triangle.vertices[0].pos)
    cross = np.cross(edge_1, edge_2)           
    pos = triangle.vertices[0].pos + cross / np.sqrt(np.linalg.norm(cross))  

    return Vertex(pos=pos, mesh=triangle.mesh)

#--- ---#

def compute_affine_transformation(triangle, deformed_triangle):

    'Returns the affine transformation(3x3 matrix) of the source triangle to the deformed triangle.'
    return np.matmul(deformed_triangle.V, triangle.V_inv)

#--- ---#

def build_A(mesh):
    'Returns the system of linear equations A'
    columns_number = len(mesh.vertices) + len(mesh.triangles)
    rows_number = (max(t.index for t in mesh.triangles) + 1) * 3 #better way? not sure there's need for max here

    A = np.zeros((rows_number, columns_number)) #scipy.sparse ?
    for triangle in mesh.triangles:
        fourth_vertex_column = len(mesh.vertices) + triangle.index
        for column in range(3):
            s = triangle.V_inv[:, column] #only take one column at time
            row_index = 3 * triangle.index  + column
            
            A[row_index, triangle.vertices[0].index] = -(s[0] + s[1] + s[2])
            A[row_index, triangle.vertices[1].index] = s[0]
            A[row_index, triangle.vertices[2].index] = s[1]
            A[row_index, fourth_vertex_column] = s[2]

    return A

#--- ---#

def build_c(target_mesh):
    'returns c, a vector containing all the values from the source triangle transformations'
    c = {}
    rows_number = (max(t.index for t in target_mesh.triangles) + 1) * 3 #better way? not sure there's need for max here

    for axis_index,axis in enumerate(['x','y','z']):
        c[axis] = np.zeros(rows_number)  
        for target_triangle in target_mesh.triangles:
            source_triangle = target_triangle.corresponding_triangle
            for column in range(3):
                row_index = 3 * target_triangle.index + column
                c[axis][row_index] = source_triangle.affine_transformation[axis_index][column]
    return c

#--- ---#

def compute_deformation_smoothness(mesh, A):
    'As, all transformations for adj triangles should be equal'
    processed_pairs = set()
    rows = []
    for triangle in mesh.triangles:
        for adj_triangle in triangle.adj_triangles:
            processed_pair = frozenset([triangle.index, adj_triangle.index]) #first time using frozenset, nice
            if processed_pair not in processed_pairs: #avoid computing pairs multiple times
                processed_pairs.add(processed_pair)
                for column in range(3):
                    Ti_row = 3*triangle.index + column
                    Tj_row = 3*adj_triangle.index + column #T of adj triangle
                    rows.append(A[Ti_row] - A[Tj_row])
    As = np.array(rows)
    return As

#--- ---#

def compute_deformation_identity(mesh): 
    'Ci, prevent the deformation smoothness to generate to drastic change in the shape'

    identity_matrix = np.eye(3)

    result = 0.0
    for triangle in mesh.triangles:
        result += np.linalg.norm(np.subtract(triangle.affine_transformation,identity_matrix), 'fro') **2
                    
    return result

#--- ---#

def closest_valid_point_term(input_mesh, deform_mesh):
    '''
    input_mesh: input mesh we want to "morph" 
    deform_mesh: mesh we want to deform to look like input
    Build Ac and cc, closest point terms
    '''

    input_mesh_vertices_pos = [input_mesh.id_vertices_dict[key].pos for key in input_mesh.id_vertices_dict.keys()] #would be a good idead to find proper name there
    tree = KDTree(input_mesh_vertices_pos)

    def get_nearest_valid_vertex(vertex):

        distance, nearest_vertex_indices = tree.query(vertex.pos, k=20) #k impacts performance, 20 seems a ok compromise but could be changed dependings on the meshes
        nearest_valid_vertex = None

        for neareast_vertex_index in nearest_vertex_indices:
            nearest_vertex = input_mesh.id_vertices_dict[neareast_vertex_index]
            angle = angle_between(v1=vertex.normal, v2=nearest_vertex.normal)

            if angle < 90: #to be valid, the angle between the normals has to be <90, for exemple, to avoid moving from inner to outer lips
                nearest_valid_vertex = nearest_vertex
                return nearest_valid_vertex
                
        if not nearest_valid_vertex: #if there is no valid point we take the closest 
            nearest_valid_vertex = input_mesh.id_vertices_dict[nearest_vertex_indices[0]]

        return nearest_valid_vertex

    def get_nearest_point_triangles(vertex, nearest_vertex):

        best_point = None
        last_distance = 999999 #there's probably a better way than setting this number?
        for triangle in nearest_vertex.triangles:
            nearest_point, distance = closest_point_to_triangle(triangle=triangle, point = vertex.pos)
            if distance < last_distance:
                last_distance = distance
                best_point = nearest_point
        return best_point, last_distance

    pairs = []
    for vertex in deform_mesh.vertices:
        nearest_vertex = get_nearest_valid_vertex(vertex=vertex) #we get the nearest source vertex for each target vertex 
        nearest_point_pos, distance =  get_nearest_point_triangles(vertex=vertex, nearest_vertex=nearest_vertex) #we get the closest point on each triangles shared by nearest vertex to target vertex
        pairs.append([vertex, nearest_point_pos])

    #Build A closest point term
    Ac = np.zeros((len(pairs), len(deform_mesh.vertices) + len(deform_mesh.triangles)))
    for index, (target_vertex, nearest_vertex) in enumerate(pairs):
        Ac[index, target_vertex.index] = 1.0
    
    #Build c closest point term
    Cc = {} #we have 1 c for each axis x,y,z
    for axis_index,axis in enumerate(['x','y','z']):
        Cc[axis] = np.zeros(len(pairs))
        for index, (target_vertex, nearest_vertex) in enumerate(pairs):        
            Cc[axis][index] = nearest_vertex[axis_index]
            
    return Ac, Cc

#--- ---#

def build_Ci(mesh): 
    'Returns the c identity for a mesh'
    identity = np.eye(3) #3x3 matrix with 1 in the diagonals
    c = {}
    rows_number = (max(t.index for t in mesh.triangles) + 1) * 3 #better way? not sure there's need for max here

    for axis_index,axis in enumerate(['x','y','z']): #c for each axis
        c[axis] = np.zeros(rows_number)  
        for triangle in mesh.triangles:
            for column in range(3):
                row_index = 3 * triangle.index + column
                c[axis][row_index] = identity[column][axis_index] 
    return c

#--- --- ---#

def apply_marker_constraints_to_A(A,mesh, markers):
    '''
    markers -> pair of two vertices, first element is from target mesh, second is from source mesh. Source mesh "morphs" into target
    returns A once markers have been applied
    '''
    A = A.tocsr()  #Compressed Sparse Row format

    mesh_markers_id = [target_vertex.index for source_vertex, target_vertex in markers]
    free_vertex_indices = sorted(list(mesh.vertices_id - set(mesh_markers_id)))
    A_new = A[:, free_vertex_indices]

    return A_new, free_vertex_indices

#--- --- ---#

def apply_marker_constraints_to_c(A,c_full, markers, axis):
    '''
    markers -> pair of two vertices, first element is from target mesh, second is from source mesh. Source mesh "morphs" into target
    returns c once markers have been applied
    '''
    A = A.tocsr() #Compressed Sparse Row format
    mesh_markers_id = [target_vertex.index for source_vertex, target_vertex in markers]
    markers_positions = np.array([source_vertex.pos[axis] for source_vertex, target_vertex in markers])
    
    A_markers = A[:, mesh_markers_id]
    c_full = c_full - A_markers @ markers_positions

    return c_full

#--- --- ---#

def solve_deformation(Ai,As,Ac,
                      ci,cs,cc,
                      wi,ws,wc,
                      mesh,markers):
    'solves the deformation of the mesh to morph into the other mesh'

    A_total = sparse.vstack([
        wi*Ai,
        ws*As,
        wc*Ac])
    
    A_new, free_vertex_indices = apply_marker_constraints_to_A(A=A_total, mesh=mesh, markers=markers) #free indices are markers and they move to target pos

    ATA = A_new.T @ A_new #left hand side, ATA -> (A.T means A transverse)
          
    results = np.zeros((len(mesh.vertices) + len(mesh.triangles), #the number of columns of A  is equal to the numberof vertices plus the number of triangles of the target mesh
                         3)) # 3rows -> x,y,z
    for source_vertex, target_vertex in markers:
        results[target_vertex.index] = source_vertex.pos
    

    for i,axis in enumerate(['x','y','z']):
        c_full = np.concatenate([ #mult by the weights
            wi * ci[axis], 
            ws * cs, 
            wc * cc[axis]
            ])
        
        c_new = apply_marker_constraints_to_c(A=A_total, c_full=c_full,markers=markers, axis=i) #disgusting name
        right_hand_side = A_new.T @ c_new #right hand matrix -> AT*c

        results[free_vertex_indices, i] = spsolve(ATA, right_hand_side) 

    return results[:len(mesh.vertices)]

#--- --- ---#

def compute_correspondence_map(input_mesh, deform_mesh):
    '''
    input_mesh: input mesh we want to "morph" 
    deform_mesh: mesh deformed to look like input
    assigns to each input mesh triangle the nearest valid triangle on deform mesh
    '''

    cached_centroids_pos = [deform_mesh.id_triangles_dict[key].cached_centroid for key in deform_mesh.id_triangles_dict.keys()]
    tree = KDTree(cached_centroids_pos)


    def get_nearest_valid_triangle(triangle, mesh):
        '''
        triangle: source triangle
        mesh: the mesh we want our closest triangle to be from      #reformulate that 
        '''

        distance, nearest_triangle_indices = tree.query(triangle.centroid, k=15) #k 15 seems good but could be changed dependings on the meshes

        for distance, neareast_vertex_index in zip(distance, nearest_triangle_indices):
            nearest_triangle = mesh.id_triangles_dict[neareast_vertex_index]
            angle = angle_between(v1 = triangle.normal, v2=nearest_triangle.cached_normal)
            if angle < 90:
                return nearest_triangle

        return mesh.id_triangles_dict[nearest_triangle_indices[0]] #default if nothing found with angle < 90

    for triangle in input_mesh.triangles:
        nearest_valid_triangle = get_nearest_valid_triangle(triangle=triangle, mesh=deform_mesh)
        triangle.corresponding_triangle = nearest_valid_triangle #assign to each triangle the triangle with the closest cached centroid and angle < 90


#--- --- ---#

def transfer_deformation(source_mesh, deformed_mesh, target_mesh, marker_pairs):

    start_time = time.time()
    
    if not source_mesh and not deformed_mesh and not target_mesh:
        return 'Please load all the relevant meshes'

    #4th vertex for each pair of source and deformed mesh triangles , then compute affine tranformation for each source mesh triangle
    for source_triangle_index, deformed_triangle_index in zip(source_mesh.id_triangles_dict.keys(), deformed_mesh.id_triangles_dict.keys()):

        source_triangle = source_mesh.id_triangles_dict[source_triangle_index]
        deformed_triangle = deformed_mesh.id_triangles_dict[deformed_triangle_index]

        source_triangle.fourth_vertex = compute_fourth_vertex(triangle=source_triangle)
        deformed_triangle.fourth_vertex = compute_fourth_vertex(triangle=deformed_triangle)

        source_triangle.affine_transformation = compute_affine_transformation(triangle=source_triangle, deformed_triangle=deformed_triangle)

    #4th vertex for each target triangle
    for triangle in target_mesh.triangles:
        triangle.fourth_vertex = compute_fourth_vertex(triangle=triangle)


    #--- Building correspondence map ---#
    #We deform the source mesh into the target mesh
    #using the cached position i.e -> the mesh vertices aren't really moved in the scene but we keep track of it

    #build system of linear equations
    A = build_A(source_mesh)

    #deformation smoothness -> Es
    As = compute_deformation_smoothness(mesh=source_mesh, A=A)
    Cs = np.zeros(As.shape[0])

    #deformation identity -> Ei
    Ai = A #identity is the same as A
    Ci = build_Ci(mesh=source_mesh)

    ws = 1.0    
    wi = 0.001  #ws and wi don't change during the minimization problem
    wc_steps = [0, 1, 10, 50, 250, 1000, 2000, 3000, 5000]  #we increase wc from 0 to 5000 to match the target

    for i,wc in enumerate(wc_steps):

        #closest valid point term -> Ec
        Ac,Cc = closest_valid_point_term(input_mesh=target_mesh, deform_mesh=source_mesh) #recomputed for each wc step

        new_positions = solve_deformation(
                        Ai=Ai, As=As, Ac=Ac,
                        ci=Ci, cs=Cs, cc=Cc,
                        wi=wi, ws=ws, wc=wc,
                        mesh=source_mesh, markers=marker_pairs)

        for vertex in source_mesh.vertices:
            vertex.cached_pos = new_positions[vertex.index] #new position once we solved for the weights
        
    #for each target triangle, the corresponding source triangle is directly stored in triangle.corresponding_triangle attribute
    compute_correspondence_map(input_mesh=target_mesh, deform_mesh=source_mesh) 

    #--- ---#
    #c -> all values for source triangle transformation
    #A columns correspond to to target vertices , rows represent triangle pairings
    #x~ is what we’re solving for: the deformed positions of the target mesh vertices

    A = build_A(mesh=target_mesh)
    c = build_c(target_mesh=target_mesh)

    ATA = A.T @ A

    results = np.zeros((len(target_mesh.vertices) + len(target_mesh.triangles), 3))

    #minimization
    for i, axis in enumerate(['x', 'y', 'z']):

        right_hand_side = A.T @ c[axis]
        results[:, i] = spsolve(ATA, right_hand_side)

    new_positions = results[:len(target_mesh.vertices)]

    #moving each vertices to their target position
    for vertex in target_mesh.vertices:
        vertex.pos = new_positions[vertex.index]


    end_time = time.time()
    print(f'time elapsed: {end_time-start_time}')
        
#--- --- ---#

