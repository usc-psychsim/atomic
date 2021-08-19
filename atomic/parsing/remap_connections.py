# -*- coding: utf-8 -*-
"""
Created on Wed Jul 28 15:33:41 2021
@author: E10849042
Function to read a map_file (dictionary) and returns remapped locations after 
grouping child_locations under a parent room according to
a specified maximum connectivity limit.
Usage: 
  new_neighbors, new_connections, name_transformations, new_dict, original_dict = transformed_connections(map_file)
  
** Required arguments: 
     map_file -- input map file dictionary
     
Outputs:
  >> new_connections : List of mew connections after map transformation
  >> name_transformations : Dictionary for looking up the name transformations from old to new locations
  >> new_dict : Dictionary of new locations, and the grouping of the original locations to form the new locations
  >> original_dict: Optional output - to check the connectivity in the input map file.  
  
"""


import re
partition_hallways = 0 # Flag for partitioning hallways. Set 0 if hallways do not need to be partitioned.

def transformed_connections(input_map):
  
  def sorted_list( l ):
    """ Sorts a given alphanumeric list
 
    Required arguments:
    l -- The list to be sorted.
 
    """
    convert = lambda text: int(text) if text.isdigit() else text
    alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
    return sorted(l, key = alphanum_key)
  
  def get_parent_room (string_in):
    """Return parent room for a location. If no child location, returns the input.
    
    Required arguments: 
      
      string_in -- location name (string)
    """
    if "_" in string_in:
      return string_in[0:string_in.index('_')]
    else:
      return string_in
  
  # Creating the original Dictionary of connections
  original_dict = {}
  original_dict["original_locations"] = []
  original_dict["num_child_locations"] = []
  
  for k in range(len(input_map["locations"])):
      if int('child_locations' in input_map["locations"][k].keys()) == 1:
          original_dict["num_child_locations"].append([input_map["locations"][k]["id"],len(input_map["locations"][k]["child_locations"])])
      elif int('part' in input_map["locations"][k]["type"]) == 1:
          original_dict["original_locations"].append(input_map["locations"][k]['id'])
      elif  int('part' in input_map["locations"][k]["type"]) == 0 and int('child_locations' in input_map["locations"][k].keys()) == 0 :
          original_dict["original_locations"].append(input_map["locations"][k]['id'])
  
  original_dict["num_neighbors"] = [0 for _ in range(len(original_dict["original_locations"]))]
  original_dict["original_neighbors"] = [[] for _ in range(len(original_dict["original_locations"]))]
  
  for k in range(len(input_map["connections"])):
      for j in range(len(input_map["connections"][k]["connected_locations"])):
          
          original_dict["original_neighbors"][original_dict["original_locations"].index(input_map["connections"][k]["connected_locations"][j])].append(input_map["connections"][k]["connected_locations"][:j]
   
                                                                                                                                                + input_map["connections"][k]["connected_locations"][j+1:]) 
            
  for k in range(len(original_dict["original_neighbors"])):
      original_dict["original_neighbors"][k] = list(set(sum(original_dict["original_neighbors"][k], [])))
      original_dict["num_neighbors"][k] = len(original_dict["original_neighbors"][k])
  
  # Creating the new Dictionary of connections
          
  new_dict = {}  
  original_dict["indices_connected"] = [] 
  new_dict["grouped_original_locations"] = []
  new_dict["neighbors"] = []  
       
  sum_connection = 0
  count = 0
  conn_thresh = 14 # maximum number of connections to look for combining
  
  
  for k in range(len(original_dict["original_locations"])):
      count += 1
      sum_connection += original_dict["num_neighbors"][k]
  
      if k > 0 and get_parent_room(original_dict["original_locations"][k]) !=  get_parent_room(original_dict["original_locations"][k-1]):
          new_dict["grouped_original_locations"].append(list(original_dict["original_locations"][max(0, k - count) : k]))
          
          lst = list(range(max(0, k - count), k))
          original_dict["indices_connected"].append(lst)
          new_dict["neighbors"].append(sorted_list(list(set().union(*original_dict["original_neighbors"][lst[0]:lst[-1] + 1]))))
          sum_connection = original_dict["num_neighbors"][k]
          count = 0
      elif sum_connection > conn_thresh and '_' in original_dict["original_locations"][k]:
        if (original_dict["original_locations"][k][0:original_dict["original_locations"][k].index('_')] 
        in original_dict["original_locations"][k-1]) :
        
          new_dict["grouped_original_locations"].append(list(original_dict["original_locations"][max(0, k - count) : k]))
          lst = list(range(max(0, k - count), k))
          original_dict["indices_connected"].append(lst)
          new_dict["neighbors"].append(sorted_list(list(set().union(*original_dict["original_neighbors"][lst[0]:lst[-1] + 1]))))
          sum_connection = original_dict["num_neighbors"][k]
          count = 0
  new_dict["grouped_original_locations"].append(list(original_dict["original_locations"][original_dict["indices_connected"][-1][-1] + 1::]))  
  new_dict["neighbors"].append(sorted_list(list(set().union(*original_dict["original_neighbors"][original_dict["indices_connected"][-1][-1] + 1:]))))
  original_dict["indices_connected"].append(list(range(original_dict["indices_connected"][-1][-1] + 1,len(original_dict["original_locations"]))))
  
  # renaming new connections
  new_dict["new_locations"] = [] 
  count = 0
  for k in range(len(new_dict["grouped_original_locations"])):
      if k == 0 and '_' in new_dict["grouped_original_locations"][k][0]:
        new_dict["new_locations"].append (get_parent_room(new_dict["grouped_original_locations"][k][0]) + '_'+chr(65 + count))
        count += 1
      elif k ==0 and '_' not in new_dict["grouped_original_locations"][k][0]:
        new_dict["new_locations"].append (get_parent_room(new_dict["grouped_original_locations"][k][0]))
      elif k > 0 and '_' in new_dict["grouped_original_locations"][k][0] and \
      get_parent_room(new_dict["grouped_original_locations"][k][0]) == get_parent_room(new_dict["grouped_original_locations"][k - 1][0]):
        new_dict["new_locations"].append (get_parent_room(new_dict["grouped_original_locations"][k][0]) + '_'+chr(65 + count))
        count += 1
      elif k > 0 and '_' in new_dict["grouped_original_locations"][k][0] and \
      get_parent_room(new_dict["grouped_original_locations"][k][0]) != get_parent_room(new_dict["grouped_original_locations"][k - 1][0]):
        count = 0
        new_dict["new_locations"].append (get_parent_room(new_dict["grouped_original_locations"][k][0]) + '_'+chr(65 + count))
        count += 1
      else : 
        new_dict["new_locations"].append (get_parent_room(new_dict["grouped_original_locations"][k][0]))
        count = 0
  
  # Lookup dictionary for transformation of location names
  name_transformations = {}  
  for orig in original_dict["original_locations"]:
      for j in range(len(new_dict["grouped_original_locations"])):
        if orig in new_dict['grouped_original_locations'][j]:
          name_transformations[orig] = new_dict['new_locations'][j]
  
  new_connections = []  
  for k in range(len(new_dict["new_locations"])): 
    for j in range((len(new_dict["neighbors"][k]))):
      if new_dict["new_locations"][k] != name_transformations[new_dict["neighbors"][k][j]] and \
      [new_dict["new_locations"][k],name_transformations[new_dict["neighbors"][k][j]]] not in new_connections and \
      [name_transformations[new_dict["neighbors"][k][j]],new_dict["new_locations"][k]] not in new_connections:
        new_connections.append([new_dict["new_locations"][k],name_transformations[new_dict["neighbors"][k][j]]])
  
  new_neighbors = [[] for _ in range(len(new_dict["neighbors"]))]
  for k in range(len(new_dict["neighbors"])):
    for j in range(len(new_dict["neighbors"][k])):
      if name_transformations[new_dict["neighbors"][k][j]] not in new_neighbors[k]:
        new_neighbors[k].append(name_transformations[new_dict["neighbors"][k][j]])
  
  
  ################ Breaking down hallways manually ######################

# ***NOTE: The following manual breaking down of hallways is based on the assumption that conn_thresh = 4
# **** If a different threshold of maximum connectivity is chosen, the following will not work, and again a manual 
# breaking down of the hallways may be required, depending on conn_thresh value

#########################################################################
  if partition_hallways == 1 and conn_thresh == 4:
    print ('Hallways partitioned along with grouping child locations')
    #---------------------------------------------------------------#
    # Breaking down 'Conference Corridor West <ccw>'
    #---------------------------------------------------------------#
    del new_neighbors[new_dict["new_locations"].index("ccw")]
    del (new_dict["neighbors"][new_dict["new_locations"].index("ccw")])
    del (new_dict["grouped_original_locations"][new_dict["new_locations"].index("ccw")])
    del (new_dict["new_locations"][new_dict["new_locations"].index("ccw")])
    
    new_dict["new_locations"].append('ccw_A')
    new_dict["neighbors"].append(['mcw', 'oba_3', 'cf_2'])
    new_neighbors.append([name_transformations[new_dict["neighbors"][-1][k]] for k in range(len(new_dict["neighbors"][-1]))])
    
    new_dict["new_locations"].append('ccw_B')
    new_dict["neighbors"].append(['lib_3', 'rrc', 'jc_2', 'crc'])
    new_neighbors.append([name_transformations[new_dict["neighbors"][-1][k]] for k in range(len(new_dict["neighbors"][-1]))])
    
    new_dict["new_locations"].append('ccw_C')
    new_dict["neighbors"].append(['kco_12', 'ccn'])
    new_neighbors.append([name_transformations[new_dict["neighbors"][-1][k]] for k in range(len(new_dict["neighbors"][-1]))])
    
    
    #---------------------------------------------------------------#
    # Breaking down 'Conference Corridor East <cce>'
    #---------------------------------------------------------------#
    del new_neighbors[new_dict["new_locations"].index("cce")]
    del (new_dict["neighbors"][new_dict["new_locations"].index("cce")])
    del (new_dict["grouped_original_locations"][new_dict["new_locations"].index("cce")])
    del (new_dict["new_locations"][new_dict["new_locations"].index("cce")])
    
    
    new_dict["new_locations"].append('cce_A')
    new_dict["neighbors"].append(['mcw', 'r110_6', 'cf_8', 'r109_7'])
    new_neighbors.append([name_transformations[new_dict["neighbors"][-1][k]] for k in range(len(new_dict["neighbors"][-1]))])
    
    new_dict["new_locations"].append('cce_B')
    new_dict["neighbors"].append(['rrc', 'r108_6', 'r107_6'])
    new_neighbors.append([name_transformations[new_dict["neighbors"][-1][k]] for k in range(len(new_dict["neighbors"][-1]))])
    
    new_dict["new_locations"].append('cce_C')
    new_dict["neighbors"].append(['crc', 'r106_8', 'r105_7', 'r104_6'])
    new_neighbors.append([name_transformations[new_dict["neighbors"][-1][k]] for k in range(len(new_dict["neighbors"][-1]))])
    
    new_dict["new_locations"].append('cce_D')
    new_dict["neighbors"].append(['ccn', 'r103_5', 'r102_4'])
    new_neighbors.append([name_transformations[new_dict["neighbors"][-1][k]] for k in range(len(new_dict["neighbors"][-1]))])
    
    #---------------------------------------------------------------#
    # Breaking down 'Main Corridor West <mcw>'
    #---------------------------------------------------------------#
    del new_neighbors[new_dict["new_locations"].index("mcw")]
    del (new_dict["neighbors"][new_dict["new_locations"].index("mcw")])
    del (new_dict["grouped_original_locations"][new_dict["new_locations"].index("mcw")])
    del (new_dict["new_locations"][new_dict["new_locations"].index("mcw")])
    
    
    new_dict["new_locations"].append('mcw_A')
    new_dict["neighbors"].append(['so', 'ccw', 'cce', 'ca_7'])
    new_neighbors.append([name_transformations[new_dict["neighbors"][-1][k]] for k in range(len(new_dict["neighbors"][-1]))])
    
    new_dict["new_locations"].append('mcw_B')
    new_dict["neighbors"].append(['ca_5', 'el_3'])
    new_neighbors.append([name_transformations[new_dict["neighbors"][-1][k]] for k in range(len(new_dict["neighbors"][-1]))])
    
    #---------------------------------------------------------------#
    # Breaking down 'Main Corridor East <mce>'
    #---------------------------------------------------------------#
    del new_neighbors[new_dict["new_locations"].index("mce")]
    del (new_dict["neighbors"][new_dict["new_locations"].index("mce")])
    del (new_dict["grouped_original_locations"][new_dict["new_locations"].index("mce")])
    del (new_dict["new_locations"][new_dict["new_locations"].index("mce")])
    
    
    new_dict["new_locations"].append('mce_A')
    new_dict["neighbors"].append(['el_3', 'sdc_22', 'scw', 'scc'])
    new_neighbors.append([name_transformations[new_dict["neighbors"][-1][k]] for k in range(len(new_dict["neighbors"][-1]))])
    
    new_dict["new_locations"].append('mce_B')
    new_dict["neighbors"].append(['sce'])
    new_neighbors.append([name_transformations[new_dict["neighbors"][-1][k]] for k in range(len(new_dict["neighbors"][-1]))])
    
    
    #---------------------------------------------------------------#
    # Breaking down 'Storage Corridor West <scw>'
    #---------------------------------------------------------------#
    del new_neighbors[new_dict["new_locations"].index("scw")]
    del (new_dict["neighbors"][new_dict["new_locations"].index("scw")])
    del (new_dict["grouped_original_locations"][new_dict["new_locations"].index("scw")])
    del (new_dict["new_locations"][new_dict["new_locations"].index("scw")])
    
    new_dict["new_locations"].append('scw_A')
    new_dict["neighbors"].append(['mce', 'sra', 'sri'])
    new_neighbors.append([name_transformations[new_dict["neighbors"][-1][k]] for k in range(len(new_dict["neighbors"][-1]))])
    
    new_dict["new_locations"].append('scw_B')
    new_dict["neighbors"].append(['src', 'srj','srk','sre'])
    new_neighbors.append([name_transformations[new_dict["neighbors"][-1][k]] for k in range(len(new_dict["neighbors"][-1]))])
    
    new_dict["new_locations"].append('scw_C')
    new_dict["neighbors"].append(['srg', 'srl', 'scn_2'])
    new_neighbors.append([name_transformations[new_dict["neighbors"][-1][k]] for k in range(len(new_dict["neighbors"][-1]))])
    
    #---------------------------------------------------------------#
    # Breaking down 'Storage Corridor Center <scc>'
    #---------------------------------------------------------------#
    del new_neighbors[new_dict["new_locations"].index("scc")]
    del (new_dict["neighbors"][new_dict["new_locations"].index("scc")])
    del (new_dict["grouped_original_locations"][new_dict["new_locations"].index("scc")])
    del (new_dict["new_locations"][new_dict["new_locations"].index("scc")])
    
    new_dict["new_locations"].append('scc_A')
    new_dict["neighbors"].append(['mce', 'srm_2', 'srq', 'srn_2'])
    new_neighbors.append([name_transformations[new_dict["neighbors"][-1][k]] for k in range(len(new_dict["neighbors"][-1]))])
    
    new_dict["new_locations"].append('scc_B')
    new_dict["neighbors"].append(['srr', 'sro_2','srp_2','srs'])
    new_neighbors.append([name_transformations[new_dict["neighbors"][-1][k]] for k in range(len(new_dict["neighbors"][-1]))])
    
    new_dict["new_locations"].append('scc_C')
    new_dict["neighbors"].append(['scn_4'])
    new_neighbors.append([name_transformations[new_dict["neighbors"][-1][k]] for k in range(len(new_dict["neighbors"][-1]))])
    
    
    #---------------------------------------------------------------#
    # Breaking down 'Storage Corridor East <sce>'
    #---------------------------------------------------------------#
    del new_neighbors[new_dict["new_locations"].index("sce")]
    del (new_dict["neighbors"][new_dict["new_locations"].index("sce")])
    del (new_dict["grouped_original_locations"][new_dict["new_locations"].index("sce")])
    del (new_dict["new_locations"][new_dict["new_locations"].index("sce")])
    
    new_dict["new_locations"].append('sce_A')
    new_dict["neighbors"].append(['mce', 'srt', 'sru', 'srv'])
    new_neighbors.append([name_transformations[new_dict["neighbors"][-1][k]] for k in range(len(new_dict["neighbors"][-1]))])
    
    new_dict["new_locations"].append('sce_B')
    new_dict["neighbors"].append(['scn_1'])
    new_neighbors.append([name_transformations[new_dict["neighbors"][-1][k]] for k in range(len(new_dict["neighbors"][-1]))])
    


    #---------------------------------------------------------------#
    # Modifying the list of new connections
    #---------------------------------------------------------------#
    connections_to_remove = []
    for k in range(len(new_connections)):
      if any (name in new_connections[k] for name in ['ccw', 'cce', 'mcw', 'mce', 'scw', 'scc', 'sce']):
        connections_to_remove.append(k)
    
    new_connections = [i for j, i in enumerate(new_connections) if j not in connections_to_remove]
    
    ind_start_hallway_partition = new_dict["new_locations"].index("ccw_A") # First hallway to be broken down is <ccw>
    
    for k in range(ind_start_hallway_partition, len(new_dict["new_locations"])): 
      for j in range((len(new_neighbors[k]))):
        if new_dict["new_locations"][k] != new_neighbors[k][j] and \
        [new_dict["new_locations"][k],new_neighbors[k][j]] not in new_connections and \
        [new_neighbors[k][j],new_dict["new_locations"][k]] not in new_connections:
          new_connections.append([new_dict["new_locations"][k],new_neighbors[k][j]])
  
  return  new_connections, name_transformations, new_dict, original_dict
