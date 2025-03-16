



'''
# Delete an item
@app.route('/delete/<int:id>')
def delete(id:int):
    delete_task = MyTask.query.get_or_404(id)
    try:
        db.session.delete(delete_task)
        db.session.commit()
        return redirect('/')
    
    except Exception as e:
        return f'Error: {e}'
    
@app.route('/edit/<int:id>', methods = ['GET','POST'])
def edit(id:int):
    task = MyTask.query.get_or_404(id)
    if request.method == 'POST':
        task.content = request.form['content']
        try:
            db.session.commit()
            return redirect('/')
        
        except Exception as e:
            return f'Error: {e}'
    else:
        return render_template('edit.html', task=task)
'''

