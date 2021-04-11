import subprocess # Used to run multiple times from this script
import os
from xml.dom import minidom
import random
import time
baselines_tf2_path = '/home/ryan/.local/lib/python3.6/site-packages/gym/envs/mujoco/assets/'

# Make sure already completed gen0 !!!!!!!!!!!!!!!!!!!
print('Did you already complete gen0? (yes-y or no-n')
ans = input('')
if ans == 'n':
	print('anta loha?')
	error

print('Did you make sure ant.xml in ~/.local/lib/python3.6/site-packages/gym/envs/mujoco/assets\nstarts as antg1_0.xml (cp antg1_0.xml ant.xml)? (yes-y or no-n')
ans = input('')
if ans == 'n':
	print('anta loha?')
	error
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

def update_Al(traj,prev_gen,new_gen,i): # (x)
	# traj - the evolving trajectory (out of 3)
	# prev_gen - last generation executed
	# new_gen - the new generation to be executed
	# i - the value used to make increments in Al
	print('traj',traj)
	print('prev_gen',prev_gen)
	print('new_gen',new_gen)
	print('i',i)
	time.sleep(1)
	# input('')
	ankle_len = 0.2 + 0.05*i

	ant_prev = minidom.parse(baselines_tf2_path+'antg{}_{}.xml'.format(traj,prev_gen))
	body = ant_prev.getElementsByTagName('body')
	geom = ant_prev.getElementsByTagName('geom')
	geom[5].attributes['fromto'].value = '0.0 0.0 0.0 {} {} 0.0'.format(ankle_len,ankle_len)
	geom[8].attributes['fromto'].value = '0.0 0.0 0.0 {} {} 0.0'.format(-ankle_len,ankle_len)
	geom[11].attributes['fromto'].value = '0.0 0.0 0.0 {} {} 0.0'.format(-ankle_len,-ankle_len)
	geom[14].attributes['fromto'].value = '0.0 0.0 0.0 {} {} 0.0'.format(ankle_len,-ankle_len)
	
	os.chdir('../../')
	os.chdir('.local/lib/python3.6/site-packages/gym/envs/mujoco/assets/')
	with open('antg{}_{}.xml'.format(traj,new_gen),'w') as fs:
		fs.write(ant_prev.toxml())
		fs.close()

	# write to the actual xml file that will be used by the computer during execution
	with open('ant.xml','w') as fs:
		fs.write(ant_prev.toxml())
		fs.close()
	print('wrote to antg{}_{}.xml'.format(traj,new_gen))
	# input('')

	os.chdir('../../../../../../../../')
	os.chdir('Documents/Evolutionary_Tracks_run_w_bash')

def update_Hl(traj,prev_gen,new_gen,i): # (y)
	# traj - the evolving trajectory (out of 3)
	# prev_gen - last generation executed
	# new_gen - the new generation to be executed
	# i - the value used to make increments in Hl
	print('traj',traj)
	print('prev_gen',prev_gen)
	print('new_gen',new_gen)
	print('i',i)
	time.sleep(1)
	# input('')
	hip_len = 0.05 + 0.0375*i

	ant_prev = minidom.parse(baselines_tf2_path+'antg{}_{}.xml'.format(traj,prev_gen))
	body = ant_prev.getElementsByTagName('body')
	geom = ant_prev.getElementsByTagName('geom')
	geom[4].attributes['fromto'].value = '0.0 0.0 0.0 {} {} 0.0'.format(hip_len,hip_len)
	geom[7].attributes['fromto'].value = '0.0 0.0 0.0 {} {} 0.0'.format(-hip_len,hip_len)
	geom[10].attributes['fromto'].value = '0.0 0.0 0.0 {} {} 0.0'.format(-hip_len,-hip_len)
	geom[13].attributes['fromto'].value = '0.0 0.0 0.0 {} {} 0.0'.format(hip_len,-hip_len)

	body[3].attributes['pos'].value = '{} {} 0'.format(hip_len,hip_len)
	body[6].attributes['pos'].value = '{} {} 0'.format(-hip_len,hip_len)
	body[9].attributes['pos'].value = '{} {} 0'.format(-hip_len,-hip_len)
	body[12].attributes['pos'].value = '{} {} 0'.format(hip_len,-hip_len)

	os.chdir('../../')
	os.chdir('.local/lib/python3.6/site-packages/gym/envs/mujoco/assets/')
	with open('antg{}_{}.xml'.format(traj,new_gen),'w') as fs:
		fs.write(ant_prev.toxml())
		fs.close()

	# write to the actual xml file that will be used by the computer during execution
	with open('ant.xml','w') as fs:
		fs.write(ant_prev.toxml())
		fs.close()
	os.chdir('../../../../../../../../')
	os.chdir('Documents/Evolutionary_Tracks_run_w_bash')

def update_Wx(traj,prev_gen,new_gen,i): # (z)
	# traj - the evolving trajectory (out of 3)
	# prev_gen - last generation executed
	# new_gen - the new generation to be executed
	# i - the value used to make increments in Wx
	
	# for Wx it works best to be a multiplicative scaling - 1 <= i <= 5 rather than 0 <= i <= 4
	torso_size1 = 0.25/5*i
	torso_size2 = 0.2/5*i
	print('traj',traj)
	print('prev_gen',prev_gen)
	print('new_gen',new_gen)
	print('i',i)
	time.sleep(1)
	# input('')
	ant_prev = minidom.parse(baselines_tf2_path+'antg{}_{}.xml'.format(traj,prev_gen))
	body = ant_prev.getElementsByTagName('body')
	geom = ant_prev.getElementsByTagName('geom')
	geom[2].setAttribute('size','{}'.format(torso_size1))
	# Starting values
	geom[3].attributes['fromto'].value = '0.0 0.0 0.0 {} {} 0.0'.format(torso_size2,torso_size2)
	geom[6].attributes['fromto'].value = '0.0 0.0 0.0 {} {} 0.0'.format(-torso_size2,torso_size2)
	geom[9].attributes['fromto'].value = '0.0 0.0 0.0 {} {} 0.0'.format(-torso_size2,-torso_size2)
	geom[12].attributes['fromto'].value = '0.0 0.0 0.0 {} {} 0.0'.format(torso_size2,-torso_size2)

	body[2].attributes['pos'].value = '{} {} 0'.format(torso_size2,torso_size2)
	body[5].attributes['pos'].value = '{} {} 0'.format(-torso_size2,torso_size2)
	body[8].attributes['pos'].value = '{} {} 0'.format(-torso_size2,-torso_size2)
	body[11].attributes['pos'].value = '{} {} 0'.format(torso_size2,-torso_size2)

	os.chdir('../../')
	os.chdir('.local/lib/python3.6/site-packages/gym/envs/mujoco/assets/')
	with open('antg{}_{}.xml'.format(traj,new_gen),'w') as fs:
		fs.write(ant_prev.toxml())
		fs.close()

	# write to the actual xml file that will be used by the computer during execution
	with open('ant.xml','w') as fs:
		fs.write(ant_prev.toxml())
		fs.close()
	os.chdir('../../../../../../../../')
	os.chdir('Documents/Evolutionary_Tracks_run_w_bash')

def print_current_settings(traj,new_gen):
	ant_prev = minidom.parse(baselines_tf2_path+'antg{}_{}.xml'.format(traj,new_gen))
	body = ant_prev.getElementsByTagName('body')
	geom = ant_prev.getElementsByTagName('geom')
	print('\nankle values')
	print('-----------------------------------------------------------------------\n')
	print('ankle_len geom[5]',geom[5].attributes['fromto'].value)
	print('ankle_len geom[8]',geom[8].attributes['fromto'].value)
	print('ankle_len geom[11]',geom[11].attributes['fromto'].value)
	print('ankle_len geom[14]',geom[14].attributes['fromto'].value)
	print('\n---------------------------------------------------------------------')

	print('\nhip values')
	print('-----------------------------------------------------------------------')
	print('ankle_len geom[4]',geom[4].attributes['fromto'].value)
	print('ankle_len geom[7]',geom[7].attributes['fromto'].value)
	print('ankle_len geom[10]',geom[10].attributes['fromto'].value)
	print('ankle_len geom[13]',geom[13].attributes['fromto'].value)

	print('torso_size2 body[3]',body[3].attributes['pos'].value)
	print('torso_size2 body[6]',body[6].attributes['pos'].value)
	print('torso_size2 body[9]',body[9].attributes['pos'].value)
	print('torso_size2 body[12]',body[12].attributes['pos'].value)
	print('\n---------------------------------------------------------------------')

	print('\ntorso values')
	print('-----------------------------------------------------------------------\n')
	print('torso_size1 geom[2]',geom[2].attributes['size'].value)
	print('torso_size2 geom[3]',geom[3].attributes['fromto'].value)
	print('torso_size2 geom[6]',geom[6].attributes['fromto'].value)
	print('torso_size2 geom[9]',geom[9].attributes['fromto'].value)
	print('torso_size2 geom[12]',geom[12].attributes['fromto'].value)

	print('torso_size2 body[2]',body[2].attributes['pos'].value)
	print('torso_size2 body[5]',body[5].attributes['pos'].value)
	print('torso_size2 body[8]',body[8].attributes['pos'].value)
	print('torso_size2 body[11]',body[11].attributes['pos'].value)
	print('\n---------------------------------------------------------------------')

	# input('')


# After gen0, gen1_1, gen2_1, and gen3_1 have been generated
print('please input the trajectory number (1,2 or 3)')
traj = int(input(''))

print('please input the number if time iterations to train for (2e6)')
time_iters = input('')

### initialize values ###
	# range of values:
	# Al = {0.2 + 0.05*i; i = [0,1,2,3,4]} Al_high = 0.4
	# Hl = {0.05 + 0.375*i; i = [0,1,2,3,4]} Hl_high = 0.2
	# Wx = {0.25/5*i; i = [1,2,3,4,5]} Wx_high = 0.25

# (i_Al,i_Hl,i_Wx) = (0,0,1) has already been completed!!!
i_Al = 1 
i_Hl = 1
i_Wx = 2
possible_choices = [1,2,3]

for prev_gen in range(12):
	new_gen = prev_gen+1 # for readability
	# 1. flip 3-sided coin to decide which out of 3 possible perturbations to
	# 	 change: i_x or i_y or i_z = min(4,new_x or new_y or new_z)
	
	# coin_toss ...
	coin_toss = random.choice(possible_choices)
	# coin_toss = 2 # MUST BE RANDOM!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
	
	# print('------------------- old settings -----------------------')
	# print_current_settings(traj,new_gen)
	# print('i_Al old, i_Hl old, i_Wx old',i_Al, i_Hl, i_Wx)
	# print('possible_choices old',possible_choices)
	print('coin_toss',coin_toss)

	# 2. create new ant file 'antg{}_1'.format(num)
	# 	 save as ant.xml
	if coin_toss == 1 and i_Al <= 4:
		update_Al(traj,prev_gen,new_gen,i_Al)
		i_Al += 1 
	elif coin_toss == 2 and i_Hl <= 4:
		update_Hl(traj,prev_gen,new_gen,i_Hl)
		i_Hl += 1
	elif coin_toss == 3 and i_Wx <= 5:
		update_Wx(traj,prev_gen,new_gen,i_Wx)
		i_Wx += 1
	else:
		gave_a_wrong_number

	print('-------------------- new settings ----------------------')
	print_current_settings(traj,new_gen)
	print('i_Al new, i_Hl new, i_Wx new',i_Al, i_Hl, i_Wx)
	print('possible_choices new',possible_choices)
	# input('')
	
	# 3. run with load 'gen_{}_{}'.format(num,i-1) and save 'gen_{}_{}'.format(num,i)
	
	if new_gen == 1:
		log_path = '~/Documents/Evolutionary_Tracks_run_w_bash/gen{}_{}'.format(traj,new_gen)
		load_path = '~/Documents/Evolutionary_Tracks_run_w_bash/gen0'
		save_path = '/home/ryan/Documents/Evolutionary_Tracks_run_w_bash/gen{}_{}'.format(traj,new_gen)
	else:
		log_path = '~/Documents/Evolutionary_Tracks_run_w_bash/gen{}_{}'.format(traj,new_gen)
		load_path = '~/Documents/Evolutionary_Tracks_run_w_bash/gen{}_{}'.format(traj,prev_gen)
		save_path = '/home/ryan/Documents/Evolutionary_Tracks_run_w_bash/gen{}_{}'.format(traj,new_gen)

	os.chdir('../../')
	os.chdir('baselines-tf2')
	p = subprocess.Popen(['python3','-m','baselines.run','--alg=trpo_mpi','--env=Ant-v2','--num_timesteps='+time_iters,'--log_path='+log_path,'--save_path='+save_path,'--load_path='+load_path])
	p.wait()
	p.terminate()
	os.chdir('../')
	os.chdir('Documents/Evolutionary_Tracks_run_w_bash')

	if i_Al == 4+1:
		# remove 1 if it exists
		possible_choices = [i for i in possible_choices if i != 1]

	if i_Hl == 4+1:
		# remove 2 if it exists
		possible_choices = [i for i in possible_choices if i != 2]

	if i_Wx == 5+1:
		# remove 3 if it exists
		possible_choices = [i for i in possible_choices if i != 3]
