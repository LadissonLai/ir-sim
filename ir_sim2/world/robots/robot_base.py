import numpy as np
from math import inf, pi, atan2, sin, cos
from ir_sim2.log.Logger import Logger
from collections import namedtuple
from ir_sim2.util import collision_dectection_geo as cdg 

# define geometry point and segment for collision detection.
# point [x, y]
# segment [point1, point2]
# polygon [point1, point2, point3...]
# circle [x, y, r]
point_geometry = namedtuple('point', ['x', 'y'])
circle_geometry = namedtuple('circle', ['x', 'y', 'r'])

class RobotBase:

    robot_type = 'diff'  # omni, acker
    appearance = 'circle'  # shape list: ['circle', 'rectangle', 'polygon']
    state_dim = (3, 1) # the state dimension 
    vel_dim = (2, 1)  # the velocity dimension 
    goal_dim = (3, 1) # the goal dimension 
    position_dim=(2,1) # the position dimension 
    dynamic = True
    cone_type = 'Rpositive' # 'Rpositive'; 'norm2' 

    def __init__(self, id, state, vel, goal, step_time=0.1, **kwargs):

        """
            type = 'diff', 'omni', 'ackermann' 
        """
        self.id = int(id)
        self.step_time = step_time

        self.init_state = state
        self.init_vel = vel
        self.init_goal_state = goal 

        if isinstance(self.init_state, list): self.init_state = np.c_[self.init_state]
        if isinstance(self.init_vel, list): self.init_vel = np.c_[self.init_vel]
        if isinstance(self.init_goal_state, list): self.init_goal_state = np.c_[self.init_goal_state]

        self.state = self.init_state
        self.goal = self.init_goal_state
        self.vel = self.init_vel
        self.trajectory = []

        assert self.state.shape == self.state_dim and self.vel.shape == self.vel_dim and self.goal.shape == self.goal_dim

        self.arrive_mode = kwargs.get('arrive_mode', 'position') # 'state', 'position'
        self.vel_min = kwargs.get('vel_min', np.c_[[-inf, -inf]])
        self.vel_max = kwargs.get('vel_max', np.c_[[inf, inf]])
        self.goal_threshold = kwargs.get('goal_threshold', 0.1)
        # self.collision_threshold = kwargs.get('collision_threshold', 0.001)
        if isinstance(self.vel_min, list): self.vel_min = np.c_[self.vel_min]
        if isinstance(self.vel_max, list): self.vel_max = np.c_[self.vel_max]

        # flag
        self.arrive_flag = False
        self.collision_flag = False
        self.cone = None

        # noise
        self.noise = kwargs.get('noise', False)

        # Generalized inequalities
        self.G, self.g = self.gen_inequal()

        # log
        self.log = Logger('robot.log', level='info')

        # sensor
        self.lidar = None
        # if lidar_args is not None:
        #     id_list = lidar_args['id_list']

        # if lidar_args is not None and self.id in id_list:
        #     self.lidar = lidar2d(**lidar_args)
        # else:
        #     self.lidar = None
        

        # self.alpha = kwargs.get('alpha', [0.03, 0, 0, 0.03, 0, 0])
        # self.control_std = kwargs.get('control_std', [0.01, 0.01])

    def move(self, vel, stop=True, **kwargs):
        """ vel: velocity to control the robot
            stop: the robot will stop when arriving at the goal

            return: 
        """
        if isinstance(vel, list): vel = np.c_[vel]
            
        assert vel.shape == self.vel_dim and self.state.shape == self.state_dim

        if (vel < self.vel_min).any() or (vel > self.vel_max).any():
            vel = np.clip(vel, self.vel_min, self.vel_max)
            self.log.logger.warning("The velocity is clipped to be %s", vel.tolist())
        if stop:
            if self.arrive_flag or self.collision_flag:
                vel = np.zeros(self.vel_dim)

        self.trajectory.append(self.state)
        self.state = self.dynamics(self.state, vel, **kwargs)
        self.arrive_flag = self.arrive()
    
    def update_info(self, state, vel):
        # update the information of the robot manually
        self.state = state
        self.vel = vel
    
    def arrive(self):
        if self.arrive_mode == 'position':
            return np.linalg.norm(self.state[0:self.position_dim[0]] - self.goal[0:self.position_dim[0]]) <= self.goal_threshold
        elif self.arrive_mode == 'state':
            return np.linalg.norm(self.state[0:self.goal_dim[0]] - self.goal) <= self.goal_threshold

    def collision_check_point(self, point):
        # utilize the generalized inequality to judge the collision with a point
        assert point.shape == self.position_dim

        rot, trans = RobotBase.get_transform(self.state[0:2, 0:1], self.state[2, 0])
        trans_point = np.linalg.inv(rot) @ ( point - trans)

        return RobotBase.InCone(self.G @ trans_point - self.g, self.cone_type)

    def collision_check_obstacle(self, obstacle):
        
        if self.appearance == 'circle':
            robot_circle = circle_geometry(self.state[0, 0], self.state[1, 0], self.radius)  

            if obstacle.appearance == 'circle':
                obs_circle = circle_geometry(obstacle.point[0, 0], obstacle.point[1, 0], obstacle.radius)  
                if cdg.collision_cir_cir(robot_circle, obs_circle): return True 
                    
            if obstacle.appearance == 'polygon':
                obs_poly = [ point_geometry(op[0, 0], op[1, 0]) for op in obstacle.points]
                if cdg.collision_cir_poly(robot_circle, obs_poly): return True
        
        if self.appearance == 'polygon':
            robot_polygon = []
            pass
        
        return False


    def cir_cir_min_distance(self, cir_obs):
        return np.linalg.norm( self.state[0:self.position_dim[0]] - cir_obs.point) - (self.radius + cir_obs.radius)

    def cir_poly_min_distance(self, poly_obs):
        robot_point = self.state[0:self.position_dim[0]]
        pass

    def dynamics(self, vel):

        """ vel: the input velocity
            return: the next state
        """
        raise NotImplementedError

    def gen_inequal(self):
        # Calculate the matrix G and g for the Generalized inequality: G @ point <_k g, 
        # self.G, self.g = self.gen_inequal()
        raise NotImplementedError
    
    def cal_des_vel(self):
        # calculate the desired velocity
        raise NotImplementedError

    def plot(self, ax, **kwargs):
        # plot the robot in the map
        raise NotImplementedError
    
    def plot_clear(self, ax):
        # plot the robot in the map
        raise NotImplementedError

    def reset(self):
        self.state = self.init_state
        self.vel = self.init_vel
        self.goal_state = self.init_goal_state

    @staticmethod
    def InCone(point, cone_type='Rpositive'):
        if cone_type == 'Rpositive':
            return (point<=0).all()
        elif cone_type == 'norm2':
            return np.squeeze(np.linalg.norm(point[0:-1]) - point[-1]) <= 0

    @staticmethod
    def get_transform(position, orientation):
        rot = np.array([ [cos(orientation), -sin(orientation)], [sin(orientation), cos(orientation)] ])
        trans = position
        return rot, trans


    @staticmethod
    def wraptopi(radian):

        while radian > pi:
            radian = radian - 2 * pi

        while radian < -pi:
            radian = radian + 2 * pi

        return radian

    @staticmethod
    def relative_position(position1, position2, topi=True):
        diff = position2[0:RobotBase.position_dim[0]]-position1[0:RobotBase.position_dim[0]]
        dis = np.linalg.norm(diff)
        radian = atan2(diff[1, 0], diff[0, 0])

        if topi: radian = RobotBase.wraptopi(radian)

        return dis, radian
    
    







    
