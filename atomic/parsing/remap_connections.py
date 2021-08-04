# -*- coding: utf-8 -*-
"""
Created on Wed Jul 28 15:33:41 2021

@author: E10849042

Function to read a map_file (dictionary) and returns remapped locations after 
grouping child_locations under a parent room according to
a specified maximum connectivity limit.

Usage: 

  lookup_names, new_map, original_map = transformed_connections(map_file)
  
** Original map is an optional output - to check the connectivity in the input map file.   
** Required arguments: 
     map_file -- input map file dictionary


"""


import re

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
          
          original_dict["num_neighbors"][original_dict["original_locations"].index(input_map["connections"][k]["connected_locations"][j])] +=1 
          original_dict["original_neighbors"][original_dict["original_locations"].index(input_map["connections"][k]["connected_locations"][j])].append(input_map["connections"][k]["connected_locations"][:j]
                                                                                                                                                   + input_map["connections"][k]["connected_locations"][j+1:]) 
  for k in range(len(original_dict["original_neighbors"])):
      original_dict["original_neighbors"][k] = sum(original_dict["original_neighbors"][k], [])
  
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
  

  return  new_connections, name_transformations, new_dict, original_dict
