from argparse import ArgumentParser
import configparser

from psychsim.world import World

from atomic.teamwork.ac import make_ac_handlers, add_joint_activity
from atomic.teamwork.asi import make_asi, make_team

messages = [{
    "participant_id": "p1",
    "jag": {
      "id": "16085100-d769-42ff-9791-6e890e349561",
      "urn": "urn:ihmc:asist:rescue-victim",
      "children": [
        {
          "id": "ff8e5266-4de7-411e-ab37-bc295220e55b",
          "urn": "urn:ihmc:asist:access-victim",
          "children": [
            {
              "id": "2847a7e0-e6fe-426f-8bb6-1ff6d4462e6b",
              "urn": "urn:ihmc:asist:check-if-unlocked",
              "children": [],
              "inputs": {
                "victim-id": 23
              },
              "outputs": {}
            },
            {
              "id": "81eeed9e-b2d7-4f4f-b92e-31dcfea04450",
              "urn": "urn:ihmc:asist:unlock-victim",
              "children": [],
              "inputs": {
                "victim-id": 23
              },
              "outputs": {}
            }
          ],
          "inputs": {
            "victim-id": 23
          },
          "outputs": {}
        },
        {
          "id": "efc74aa5-c2bc-456b-8ba0-c8512072c8ee",
          "urn": "urn:ihmc:asist:triage-and-evacuate",
          "children": [
            {
              "id": "c53e9dea-b8d9-4862-97dd-562b536f7a83",
              "urn": "urn:ihmc:asist:triage-victim",
              "children": [
                {
                  "id": "889d5c2b-df31-4233-bc18-c07d5e45b73f",
                  "urn": "urn:ihmc:asist:stabilize",
                  "children": [],
                  "inputs": {
                    "victim-id": 23
                  },
                  "outputs": {}
                }
              ],
              "inputs": {
                "victim-id": 23
              },
              "outputs": {}
            },
            {
              "id": "2e6e5f2a-0699-40a3-851b-32a8d583afc0",
              "urn": "urn:ihmc:asist:evacuate-victim",
              "children": [
                {
                  "id": "78576ef2-64d8-4735-8c82-fc3422d7962f",
                  "urn": "urn:ihmc:asist:determine-triage-area",
                  "children": [
                    {
                      "id": "e3226fe8-13a2-407f-95ee-a05de7e6e767",
                      "urn": "urn:ihmc:asist:diagnose",
                      "children": [],
                      "inputs": {
                        "victim-id": 23
                      },
                      "outputs": {}
                    }
                  ],
                  "inputs": {
                    "victim-id": 23
                  },
                  "outputs": {}
                },
                {
                  "id": "5015c703-65a7-4620-951b-25191db2caa3",
                  "urn": "urn:ihmc:asist:move-victim-to-triage-area",
                  "children": [
                    {
                      "id": "9720f814-67e3-42b2-b746-bfe4d6d06c85",
                      "urn": "urn:ihmc:asist:relocate-victim",
                      "children": [
                        {
                          "id": "f413f054-f808-4fdc-82e2-3612321b8953",
                          "urn": "urn:ihmc:asist:pick-up-victim",
                          "children": [],
                          "inputs": {
                            "victim-id": 23
                          },
                          "outputs": {}
                        },
                        {
                          "id": "e5eadda3-31e3-4896-aa23-ac9eb1f8a05d",
                          "urn": "urn:ihmc:asist:drop-off-victim",
                          "children": [],
                          "inputs": {
                            "victim-id": 23
                          },
                          "outputs": {}
                        }
                      ],
                      "inputs": {
                        "victim-id": 23
                      },
                      "outputs": {}
                    },
                    {
                      "id": "b448b9af-b658-4639-bd48-5a6851796ec4",
                      "urn": "urn:ihmc:asist:at-proper-triage-area",
                      "children": [],
                      "inputs": {
                        "victim-id": 23
                      },
                      "outputs": {},
                      "required": True
                    }
                  ],
                  "inputs": {
                    "victim-id": 23
                  },
                  "outputs": {}
                }
              ],
              "inputs": {
                "victim-id": 23
              },
              "outputs": {}
            }
          ],
          "inputs": {
            "victim-id": 23
          },
          "outputs": {}
        }
      ],
      "inputs": {
        "victim-id": 23
      },
      "outputs": {}
    }
  }]

if __name__ == '__main__':
    # Command-line arguments
    parser = ArgumentParser()
    parser.add_argument('--config', help='Config file specifying execution parameters')
    args = vars(parser.parse_args())

    if args['config']:
        config = configparser.ConfigParser()
        config.read(args['config'])
    world = World()
    players = {name: world.addAgent(name) for name in ['p1', 'p2', 'p3']}
    acs = make_ac_handlers(config)
    team = make_team(world)
    world.addAgent(team)
    for ac in acs.values():
        ac.augment_world(world, team, players)
    team.initialize_effects(acs)
    for data in messages:
        add_joint_activity(world, world.agents[data['participant_id']], team.name, data['jag'])
    for player in players:
        agent = world.agents[player]

    asi = make_asi(world, team, players, acs, config)
    world.save('asi')
