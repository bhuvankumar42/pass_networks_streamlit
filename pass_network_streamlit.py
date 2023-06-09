import streamlit as st
from statsbombpy import sb
import pandas as pd
from mplsoccer.pitch import Pitch, VerticalPitch
from matplotlib import pyplot as plt

comp = sb.competitions()

st.title(':soccer: Pass Network Generator')
with st.sidebar:
	league = st.selectbox("League", comp.competition_name.unique())
	season = st.selectbox("Season", comp[comp['competition_name'] == league]['season_name'])
	selected = comp[(comp['competition_name'] == league) & (comp['season_name'] == season)].reset_index()
	mat = sb.matches(competition_id = selected['competition_id'][0], season_id = selected['season_id'][0])
	mat['match'] = [mat['home_team'][i] + ' vs ' + mat['away_team'][i] + ' (' + str(mat['home_score'][i]) + ':' + str(mat['away_score'][i]) + ') (' + mat['match_date'][i] + ')' for i in range(len(mat))]
	match = st.selectbox("Match", mat.match)
	min_pass_sel = st.slider("Minimum passes per 90 minutes to plot a connection", max_value = 20, value=10)
	but = st.button('Plot!')

match_id = mat['match_id'][list(mat['match']).index(match)]
home_team = mat['home_team'][list(mat['match']).index(match)]
away_team = mat['away_team'][list(mat['match']).index(match)]

def pass_network(MATCH_ID, TEAM):
	line_ups = pd.DataFrame(sb.lineups(match_id = MATCH_ID)[TEAM]).filter(['player_name', 'jersey_number'])
	events = pd.DataFrame(sb.events(match_id = MATCH_ID))
	events = events.filter(['id', 'player', 'team', 'type', 'location', 'pass_end_location', 'pass_outcome', 'pass_recipient', 'minute'])
	subs = events[events['type']=='Substitution'][events['team']==TEAM]
	if not subs.empty:
		first_sub = subs['minute'].min()
	else:
		first_sub = None
	passes = events[(events['type']=='Pass') & (events['team']==TEAM)]
	passes['pass_outcome'] = passes['pass_outcome'].fillna('Successful')
	if first_sub:
		passes = passes[passes['minute']<first_sub]
	passes['x'] = [i[0] for i in passes['location']]
	passes['y'] = [i[1] for i in passes['location']]
	passes['end_x'] = [i[0] for i in passes['pass_end_location']]
	passes['end_y'] = [i[1] for i in passes['pass_end_location']]
	passes = passes.drop(['team', 'type', 'location', 'pass_end_location'], axis = 1)
	successful = passes[passes['pass_outcome']=='Successful'].reset_index()
	successful = successful.drop('index', axis=1)
	average_locations = successful.groupby('player').agg({'x':['mean'], 'y':['mean', 'count']})
	average_locations.columns = ['x', 'y', 'count']
	average_locations_new = average_locations.merge(line_ups, left_index=True, right_on='player_name').reset_index().drop('index', axis=1)
	pass_between = successful.groupby(['player', 'pass_recipient']).id.count().reset_index()
	pass_between = pass_between.rename({'id':'pass_count'}, axis = 'columns')

	pass_between = pass_between.merge(average_locations, left_on = 'player', right_index=True)
	pass_between = pass_between.merge(average_locations, left_on = 'pass_recipient', right_index=True, suffixes=['', '_end']).reset_index().drop(['index'], axis=1)

	for i in range(len(pass_between.index)):
	    if pass_between[pass_between['player']==pass_between.pass_recipient[i]][pass_between['pass_recipient']==pass_between.player[i]].empty:
	        pass_between.loc[len(pass_between.index)] = [pass_between['pass_recipient'][i], pass_between['player'][i], 0, pass_between['x_end'][i], pass_between['y_end'][i], pass_between['count_end'][i], pass_between['x'][i], pass_between['y'][i], pass_between['count'][i]]

	pass_between = pass_between.drop(['count', 'count_end'], axis=1)
	pass_between = pass_between.merge(pass_between, left_on=['player', 'pass_recipient'], right_on = ['pass_recipient','player'], suffixes=['_1', '_2'])
	i = 0
	while True:
	    ind = pass_between[pass_between['player_1']==pass_between['pass_recipient_1'][i]][pass_between['pass_recipient_1']==pass_between['player_1'][i]].index[0]
	    pass_between = pass_between.drop(ind, axis = 0).reset_index().drop('index', axis = 1)
	    if i == pass_between.index[-1]:
	        break
	    i += 1
	    
	pass_between = pass_between.drop(['x_end_1', 'y_end_1', 'pass_recipient_1', 'pass_recipient_2', 'x_end_2', 'y_end_2'], axis = 1)
	pass_between['total_pass_between'] = pass_between['pass_count_1']+pass_between['pass_count_2']

	column_names = ['player_1', 'player_2', 'total_pass_between', 'x_1', 'y_1', 'x_2', 'y_2', 'pass_count_1', 'pass_count_2']
	pass_between = pass_between.reindex(columns=column_names)
	pass_between['total_pass_between_p90'] = [i*90/first_sub for i in pass_between['total_pass_between']]
	return pass_between, average_locations_new

def plot(pass_between_h, average_locations_h, pass_between_a, average_locations_a, min_pass):
	MAX_WIDTH = 15
	pass_between_h['width'] = (pass_between_h.total_pass_between_p90)/ (pass_between_h.total_pass_between_p90.max()) * MAX_WIDTH
	pass_between_min_h = pass_between_h[pass_between_h['total_pass_between_p90']>=min_pass]

	pass_between_a['width'] = (pass_between_a.total_pass_between_p90)/ (pass_between_a.total_pass_between_p90.max())* MAX_WIDTH
	pass_between_min_a = pass_between_a[pass_between_a['total_pass_between_p90']>=min_pass]

	pitch = VerticalPitch(pitch_type='statsbomb', pitch_color = '#000000', line_color='#C2C2C2', positional=True, positional_color='#626363', positional_linestyle='--', positional_zorder=0.7)
	fig, ax = pitch.draw(figsize=(18, 12), ncols = 2)
	fig.set_facecolor('#000000')

	arrows_h = pitch.lines(pass_between_min_h.x_1, pass_between_min_h.y_1, pass_between_min_h.x_2, pass_between_min_h.y_2, ax=ax[0], color='white', zorder=1, linewidth=pass_between_min_h.width, alpha=0.9)

	nodes_h = pitch.scatter(average_locations_h.x, average_locations_h.y, s=1200, color='#000000', edgecolors='red', ax=ax[0], linewidth=5)
	for i in range(11):
	  	pitch.annotate(average_locations_h.jersey_number[i], xy = (average_locations_h.x[i], average_locations_h.y[i]), va = 'center', ha='center', c='#ffffff', size=18, weight='bold', ax=ax[0])
	
	arrows_a = pitch.lines(pass_between_min_a.x_1, pass_between_min_a.y_1, pass_between_min_a.x_2, pass_between_min_a.y_2, ax=ax[1], color='white', zorder=1, linewidth=pass_between_min_a.width, alpha=0.9)

	nodes_a = pitch.scatter(average_locations_a.x, average_locations_a.y, s=1200, color='#000000', edgecolors='blue', ax=ax[1], linewidth=5)
	for i in range(11):
	  	pitch.annotate(average_locations_a.jersey_number[i], xy = (average_locations_a.x[i], average_locations_a.y[i]), va = 'center', ha='center', c='#ffffff', size=18, weight='bold', ax=ax[1])
	ax[0].set_title(home_team, color='#FFFFFF', size=30, va='top', y=1.05)
	ax[1].set_title(away_team, color='#FFFFFF', size=30, va='top', y=1.05)
	plt.suptitle(match, color='#FFFFFF', size=40, va='center', fontweight='bold', y=1.015)
	plt.figtext(0.08, 0, 'Only passes before first substitution are considered.', size=16, color='#C2C2C2')
	plt.figtext(0.08, -0.03, f'Lines between players shows connections of atleast {min_pass} passes per 90 minutes.', size=16, color='#C2C2C2')
	plt.figtext(0.08, -0.06, 'Line width represents number of passes.', size=16, color='#C2C2C2')
	plt.figtext(0.5, 0.95, 'Code by: Bhuvan Kumar | Data: StatsBomb', color='#C2C2C2', size=20, ha='center')
	fig.tight_layout()
	return fig

if but:
	home = pass_network(match_id, home_team)
	away = pass_network(match_id, away_team)
	network = plot(home[0], home[1], away[0], away[1], min_pass_sel)
	st.pyplot(network)

